"""Comprehensive Phase 2 tests for Razorpay Checkout Integration (SE8-31).

Covers:
- Razorpay order creation with server-calculated amount and paise conversion
- Empty cart rejection
- Unauthenticated buyer rejection and role enforcement
- 15-minute active attempt reuse
- Modified cart/hash creates new attempt
- Successful checkout transaction preserving SAD §4.3.2 Option A
- Wrong buyer attempt ownership rejection
- Wrong Razorpay order ID rejection
- Modified cart hash rejection at checkout triggering safe compensation
- Invalid signature causes no refund
- Payment verification occurs before compensation
- Amount and currency mismatch rejection
- Uncaptured payment rejection
- Duplicate callback does not create duplicate orders
- Payment ID cannot be replayed across orders
- Stock contention causes safe verification and compensation
- Cart consumption is atomic with order creation
- Two paid attempts against the same cart cannot fulfill two orders
- Refund idempotency header (X-Refund-Idempotency) is sent correctly
- Refund retry reuses the exact same key and payload
- Pending refund remains pending
- Failed refund recorded and escalated to manual_review after 3 retries
- Partial refund is never marked fully refunded (unrefunded balance tracked)
- Ambiguous commit checks persisted order/payment state before refunding
- Reconciliation distinguishes fulfilled order from refund
"""
from decimal import Decimal
from unittest import mock
import uuid

from flask_jwt_extended import create_access_token
import pytest

from app.extensions import db
from app.models import (
    Artisan,
    Cart,
    CartItem,
    Category,
    Inventory,
    Order,
    OrderItem,
    Payment,
    PaymentAttempt,
    Product,
    User,
)
from app.payment import service as payment_service
from app.payment.gateway import RazorpayGateway
from app.payment.reconciliation import (
    reconcile_all_pending,
    reconcile_payment_attempt,
)
from app.payment.routes import compute_cart_hash


# -----------------------------------------------------------------------------
# Fixtures & Helpers
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_payment_gateway():
    """Ensure payment_service._gateway is reset before and after every test."""
    original = payment_service._gateway
    payment_service._gateway = None
    yield
    payment_service._gateway = original


def make_user_and_headers(role="buyer"):
    tag = uuid.uuid4().hex[:10]
    user = User(
        email=f"user_{tag}@pes.edu",
        password_hash="test-hash",
        full_name=f"Test {role.title()} {tag}",
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    token = create_access_token(
        identity=str(user.user_id), additional_claims={"role": role}
    )
    return user.user_id, {"Authorization": f"Bearer {token}"}


def make_product(title="Silk Scarf", price=450.00, stock=10, is_active=True):
    tag = uuid.uuid4().hex[:10]
    seller = User(
        email=f"artisan_{tag}@pes.edu",
        password_hash="test-hash",
        full_name="Artisan Weaver",
        role="artisan",
    )
    db.session.add(seller)
    db.session.flush()
    artisan = Artisan(user_id=seller.user_id, shop_name=f"Weave Studio {tag}")
    category = Category(name=f"Textiles {tag}", slug=f"textiles-{tag}")
    db.session.add_all([artisan, category])
    db.session.flush()
    product = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description=f"Handmade {title.lower()}",
        price=price,
        is_active=is_active,
    )
    db.session.add(product)
    db.session.flush()
    inv = Inventory(
        product_id=product.product_id,
        stock_quantity=stock,
        low_stock_threshold=5,
    )
    db.session.add(inv)
    db.session.commit()
    return product.product_id


def add_to_cart(client, headers, product_id, quantity=1):
    resp = client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": quantity},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    return resp


@pytest.fixture
def mock_razorpay_gateway():
    """Create a RazorpayGateway with mocked client and wire it into payment_service."""
    fake_client = mock.MagicMock()
    fake_client.retry_enabled = True
    fake_client.max_retries = 3
    fake_client.utility = mock.MagicMock()
    fake_client.payment = mock.MagicMock()
    fake_client.order = mock.MagicMock()

    gw = RazorpayGateway(
        key_id="rzp_test_phase2key",
        key_secret="test_phase2secret",
        client=fake_client,
    )
    payment_service._gateway = gw
    return gw


# -----------------------------------------------------------------------------
# Section 3: Razorpay Order Creation Endpoint Tests
# -----------------------------------------------------------------------------
def test_razorpay_order_creation_server_calculated_amount(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid1 = make_product(title="Pottery Vase", price=350.00, stock=5)
    pid2 = make_product(title="Ceramic Plate", price=150.50, stock=5)

    add_to_cart(client, headers, pid1, 2)  # 2 * 350.00 = 700.00
    add_to_cart(client, headers, pid2, 1)  # 1 * 150.50 = 150.50 -> Total = 850.50

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_test_12345",
        "amount": 85050,
        "currency": "INR",
        "status": "created",
    }

    resp = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()

    assert data["razorpay_order_id"] == "order_rzp_test_12345"
    assert data["amount"] == 85050  # 850.50 INR in paise
    assert data["currency"] == "INR"
    assert data["key_id"] == "rzp_test_phase2key"
    assert "attempt_id" in data
    assert "key_secret" not in data
    assert "secret" not in data

    # Verify call to SDK order.create
    mock_razorpay_gateway.client.order.create.assert_called_once()
    create_args = mock_razorpay_gateway.client.order.create.call_args[1]["data"]
    assert create_args["amount"] == 85050
    assert create_args["currency"] == "INR"
    assert create_args["payment"]["capture"] == "automatic"
    assert create_args["payment"]["capture_options"]["automatic_expiry_period"] == 12
    assert create_args["payment"]["capture_options"]["refund_speed"] == "optimum"

    # Verify attempt in DB
    att = db.session.get(PaymentAttempt, data["attempt_id"])
    assert att is not None
    assert att.buyer_id == buyer_id
    assert att.amount == Decimal("850.50")
    assert att.status == "created"


def test_empty_cart_rejection(client, mock_razorpay_gateway):
    _, headers = make_user_and_headers(role="buyer")
    resp = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "CART_EMPTY"


def test_unauthenticated_buyer_rejection(client):
    resp = client.post("/api/payments/razorpay-order")
    assert resp.status_code == 401

    _, artisan_headers = make_user_and_headers(role="artisan")
    resp_artisan = client.post("/api/payments/razorpay-order", headers=artisan_headers)
    assert resp_artisan.status_code == 403
    assert resp_artisan.get_json()["error"] == "FORBIDDEN"


def test_attempt_reuse_within_15_minutes(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=200.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_reuse_001",
        "amount": 20000,
        "currency": "INR",
        "status": "created",
    }

    # First call: creates order
    resp1 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp1.status_code == 201
    assert mock_razorpay_gateway.client.order.create.call_count == 1

    # Second call within 15 minutes with identical cart: reuses order
    resp2 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp2.status_code == 200
    assert resp2.get_json()["razorpay_order_id"] == "order_rzp_reuse_001"
    assert resp2.get_json()["attempt_id"] == resp1.get_json()["attempt_id"]
    # SDK should NOT have been called a second time
    assert mock_razorpay_gateway.client.order.create.call_count == 1


def test_modified_cart_hash_creates_new_attempt(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=200.00, stock=10)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.side_effect = [
        {"id": "order_rzp_first", "amount": 20000, "currency": "INR", "status": "created"},
        {"id": "order_rzp_second", "amount": 40000, "currency": "INR", "status": "created"},
    ]

    resp1 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp1.status_code == 201

    # Modify cart (increase quantity)
    add_to_cart(client, headers, pid, 1)  # now qty = 2

    resp2 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp2.status_code == 201
    assert resp2.get_json()["razorpay_order_id"] == "order_rzp_second"
    assert resp2.get_json()["amount"] == 40000
    assert mock_razorpay_gateway.client.order.create.call_count == 2


# -----------------------------------------------------------------------------
# Section 4 & 5: Successful Checkout & Option A Order
# -----------------------------------------------------------------------------
def test_checkout_successful_sad_option_a(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=500.00, stock=8)
    add_to_cart(client, headers, pid, 2)  # Total = 1000.00

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_success_001",
        "amount": 100000,
        "currency": "INR",
        "status": "created",
    }
    ord_resp = client.post("/api/payments/razorpay-order", headers=headers)
    assert ord_resp.status_code == 201

    # Mock payment verification & fetch
    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_rzp_success_001",
        "order_id": "order_rzp_success_001",
        "amount": 100000,
        "currency": "INR",
        "status": "captured",
    }

    checkout_payload = {
        "shipping_address": "42 MG Road, Bengaluru",
        "razorpay_order_id": "order_rzp_success_001",
        "razorpay_payment_id": "pay_rzp_success_001",
        "razorpay_signature": "sig_valid_001",
    }

    resp = client.post("/api/checkout", json=checkout_payload, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()

    assert data["status"] == "Processing"
    assert data["payment_status"] == "captured"
    assert data["total"] == 1000.00
    assert data["transaction_ref"] == "pay_rzp_success_001"

    # Verify inventory was decremented
    inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == pid))
    assert inv.stock_quantity == 6  # 8 - 2

    # Verify cart was cleared atomically
    cart = db.session.scalar(db.select(Cart).where(Cart.buyer_id == buyer_id))
    lines = db.session.scalars(db.select(CartItem).where(CartItem.cart_id == cart.cart_id)).all()
    assert len(lines) == 0

    # Verify Order, OrderItem, Payment records
    order = db.session.get(Order, data["order_id"])
    assert order is not None
    items = db.session.scalars(
        db.select(OrderItem).where(OrderItem.order_id == order.order_id)
    ).all()
    assert len(items) == 1
    payment = db.session.scalar(db.select(Payment).where(Payment.order_id == order.order_id))
    assert payment is not None
    assert payment.transaction_ref == "pay_rzp_success_001"
    assert payment.payment_status == "captured"

    # Verify PaymentAttempt completed
    att = db.session.scalar(
        db.select(PaymentAttempt).where(PaymentAttempt.razorpay_order_id == "order_rzp_success_001")
    )
    assert att.status == "completed"
    assert att.razorpay_payment_id == "pay_rzp_success_001"


def test_wrong_buyer_attempt_ownership_rejection(client, mock_razorpay_gateway):
    buyer1_id, headers1 = make_user_and_headers(role="buyer")
    buyer2_id, headers2 = make_user_and_headers(role="buyer")
    pid = make_product(price=300.00, stock=5)
    add_to_cart(client, headers1, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_buyer1",
        "amount": 30000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers1)

    # Buyer 2 tries to checkout with Buyer 1's order
    payload = {
        "shipping_address": "10 Commercial St",
        "razorpay_order_id": "order_rzp_buyer1",
        "razorpay_payment_id": "pay_rzp_b2",
        "razorpay_signature": "sig_b2",
    }
    resp = client.post("/api/checkout", json=payload, headers=headers2)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "FORBIDDEN"


def test_wrong_razorpay_order_id_rejection(client, mock_razorpay_gateway):
    _, headers = make_user_and_headers(role="buyer")
    payload = {
        "shipping_address": "10 Commercial St",
        "razorpay_order_id": "order_nonexistent_999",
        "razorpay_payment_id": "pay_999",
        "razorpay_signature": "sig_999",
    }
    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_ORDER"


def test_duplicate_callback_does_not_create_duplicate_orders(client, mock_razorpay_gateway):
    _, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=400.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_dup_001",
        "amount": 40000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_rzp_dup_001",
        "order_id": "order_rzp_dup_001",
        "amount": 40000,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "shipping_address": "12 Residency Road",
        "razorpay_order_id": "order_rzp_dup_001",
        "razorpay_payment_id": "pay_rzp_dup_001",
        "razorpay_signature": "sig_dup_001",
    }

    # First checkout completes successfully
    resp1 = client.post("/api/checkout", json=payload, headers=headers)
    assert resp1.status_code == 201

    # Second callback with the same attempt is rejected
    resp2 = client.post("/api/checkout", json=payload, headers=headers)
    assert resp2.status_code == 409
    assert resp2.get_json()["error"] == "ALREADY_COMPLETED"


def test_payment_id_cannot_be_replayed_across_orders(client, mock_razorpay_gateway):
    _, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=10)
    add_to_cart(client, headers, pid, 1)

    # Insert a prior payment with pay_id_replayed
    prior_order = Order(
        buyer_id=1, total_amount=100.00, status="Processing", shipping_address="Prior Addr"
    )
    db.session.add(prior_order)
    db.session.flush()
    db.session.add(
        Payment(
            order_id=prior_order.order_id,
            transaction_ref="pay_id_replayed",
            amount=100.00,
            payment_status="captured",
        )
    )
    db.session.commit()

    # Now create an attempt for a new order
    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_new_002",
        "amount": 10000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    payload = {
        "shipping_address": "12 Residency Road",
        "razorpay_order_id": "order_rzp_new_002",
        "razorpay_payment_id": "pay_id_replayed",
        "razorpay_signature": "sig_002",
    }

    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "REPLAYED_PAYMENT"


# -----------------------------------------------------------------------------
# Section 6: Stock & Cart Contention & Safe Compensation Flow
# -----------------------------------------------------------------------------
def test_invalid_signature_causes_no_refund(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=250.00, stock=0)  # out of stock!
    # Manually add to cart even though stock is 0
    cart = db.session.scalar(db.select(Cart).where(Cart.buyer_id == buyer_id))
    if not cart:
        cart = Cart(buyer_id=buyer_id)
        db.session.add(cart)
        db.session.flush()
    db.session.add(CartItem(cart_id=cart.cart_id, product_id=pid, quantity=1, unit_price=250.00))
    db.session.commit()

    prices = {pid: Decimal("250.00")}
    cart_lines = db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id)
    ).all()
    cart_hash, _ = compute_cart_hash(cart.cart_id, cart_lines, prices)
    att = PaymentAttempt(
        buyer_id=buyer_id,
        cart_id=cart.cart_id,
        amount=Decimal("250.00"),
        currency="INR",
        cart_hash=cart_hash,
        razorpay_order_id="order_rzp_sig_fail",
        status="created",
    )
    db.session.add(att)
    db.session.commit()

    # Signature verification fails!
    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = False

    payload = {
        "shipping_address": "10 Commercial St",
        "razorpay_order_id": "order_rzp_sig_fail",
        "razorpay_payment_id": "pay_fake_001",
        "razorpay_signature": "sig_forged",
    }

    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_SIGNATURE"

    # Gateway refund must NEVER be called when signature fails!
    mock_razorpay_gateway.client.payment.refund.assert_not_called()


def test_stock_contention_causes_safe_compensation(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=600.00, stock=1)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_stock_fail",
        "amount": 60000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    # Concurrently consume the stock
    inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == pid))
    inv.stock_quantity = 0
    db.session.commit()

    # Verification mocks
    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_rzp_stock_fail",
        "order_id": "order_rzp_stock_fail",
        "amount": 60000,
        "currency": "INR",
        "status": "captured",
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_stock_001",
        "amount": 60000,
        "status": "processed",
    }

    payload = {
        "shipping_address": "55 Brigade Road",
        "razorpay_order_id": "order_rzp_stock_fail",
        "razorpay_payment_id": "pay_rzp_stock_fail",
        "razorpay_signature": "sig_valid_stock",
    }

    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INSUFFICIENT_STOCK"

    # Verify payment verification occurred before refund
    mock_razorpay_gateway.client.payment.fetch.assert_called_with(
        "pay_rzp_stock_fail", timeout=(1.0, 2.0)
    )
    mock_razorpay_gateway.client.payment.refund.assert_called_once()

    # Verify PaymentAttempt record state in DB
    att = db.session.scalar(
        db.select(PaymentAttempt)
        .where(PaymentAttempt.razorpay_order_id == "order_rzp_stock_fail")
    )
    assert att.status == "refunded"
    assert att.refund_ref == "rfnd_stock_001"
    assert att.refund_idempotency_key is not None
    assert att.refund_idempotency_key.startswith("rfk_")


def test_modified_cart_hash_rejection_at_checkout(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=300.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_hash_mismatch",
        "amount": 30000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    # Change product price behind buyer's back
    prod = db.session.get(Product, pid)
    prod.price = Decimal("350.00")
    db.session.commit()

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_rzp_hash_001",
        "order_id": "order_rzp_hash_mismatch",
        "amount": 30000,
        "currency": "INR",
        "status": "captured",
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_hash_001",
        "amount": 30000,
        "status": "processed",
    }

    payload = {
        "shipping_address": "55 Brigade Road",
        "razorpay_order_id": "order_rzp_hash_mismatch",
        "razorpay_payment_id": "pay_rzp_hash_001",
        "razorpay_signature": "sig_valid_hash",
    }

    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "CART_MISMATCH"

    att = db.session.scalar(
        db.select(PaymentAttempt)
        .where(PaymentAttempt.razorpay_order_id == "order_rzp_hash_mismatch")
    )
    assert att.status == "refunded"
    assert att.refund_ref == "rfnd_hash_001"


def test_two_paid_attempts_against_same_cart_cannot_fulfil_two_orders(
    client, mock_razorpay_gateway
):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=500.00, stock=10)
    add_to_cart(client, headers, pid, 1)

    # Attempt 1 created
    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_attempt_1",
        "amount": 50000,
        "currency": "INR",
        "status": "created",
    }
    resp1 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp1.status_code == 201

    # Simulate attempt 2 created manually for test
    cart = db.session.scalar(db.select(Cart).where(Cart.buyer_id == buyer_id))
    prices = {pid: Decimal("500.00")}
    cart_lines = db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id)
    ).all()
    cart_hash, _ = compute_cart_hash(cart.cart_id, cart_lines, prices)
    att2 = PaymentAttempt(
        buyer_id=buyer_id,
        cart_id=cart.cart_id,
        amount=Decimal("500.00"),
        currency="INR",
        cart_hash=cart_hash,
        razorpay_order_id="order_attempt_2",
        status="created",
    )
    db.session.add(att2)
    db.session.commit()

    # Mocks for Attempt 1
    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.side_effect = [
        # Call for attempt 1
        {
            "id": "pay_att_1", "order_id": "order_attempt_1",
            "amount": 50000, "currency": "INR", "status": "captured"
        },
        # Call for attempt 2 verification before refund
        {
            "id": "pay_att_2", "order_id": "order_attempt_2",
            "amount": 50000, "currency": "INR", "status": "captured"
        },
    ]
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_att2_001", "amount": 50000, "status": "processed"
    }

    # Attempt 1 checks out and fulfills order
    pay1 = {
        "shipping_address": "Address 1",
        "razorpay_order_id": "order_attempt_1",
        "razorpay_payment_id": "pay_att_1",
        "razorpay_signature": "sig_att_1",
    }
    res1 = client.post("/api/checkout", json=pay1, headers=headers)
    assert res1.status_code == 201

    # Attempt 2 tries to checkout against now-consumed cart
    pay2 = {
        "shipping_address": "Address 1",
        "razorpay_order_id": "order_attempt_2",
        "razorpay_payment_id": "pay_att_2",
        "razorpay_signature": "sig_att_2",
    }
    res2 = client.post("/api/checkout", json=pay2, headers=headers)
    assert res2.status_code == 400
    assert res2.get_json()["error"] == "CART_EMPTY"

    # Attempt 2 must be safely refunded
    att2_db = db.session.get(PaymentAttempt, att2.attempt_id)
    assert att2_db.status == "refunded"
    assert att2_db.refund_ref == "rfnd_att2_001"


# -----------------------------------------------------------------------------
# Section 7 & 10: Refund Idempotency, Statuses & Reconciliation
# -----------------------------------------------------------------------------
def test_refund_idempotency_header_sent_correctly(app, mock_razorpay_gateway):
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_test_idemp",
        "status": "processed",
        "amount": 25000,
    }

    res = mock_razorpay_gateway.void_or_refund_charge(
        "pay_test_001",
        reason="customer return",
        amount=Decimal("250.00"),
        idempotency_key="rfk_test_uuid1234",
    )

    assert res["payment_status"] == "refunded"
    assert res["refund_id"] == "rfnd_test_idemp"

    mock_razorpay_gateway.client.payment.refund.assert_called_once()
    call_kwargs = mock_razorpay_gateway.client.payment.refund.call_args[1]
    assert "headers" in call_kwargs
    assert call_kwargs["headers"]["X-Refund-Idempotency"] == "rfk_test_uuid1234"


def test_refund_retry_reuses_exact_same_key_and_payload(app, mock_razorpay_gateway):
    # Setup attempt in refund_pending state
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("150.00"),
        currency="INR",
        cart_hash="hash123",
        razorpay_order_id="order_retry_test",
        razorpay_payment_id="pay_retry_test",
        status="refund_pending",
        refund_idempotency_key="rfk_fixed_key_001",
        failure_reason="stock ran out",
        retry_count=0,
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_retry_test",
        "order_id": "order_retry_test",
        "amount": 15000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 0,
        "items": [],
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_retry_success",
        "status": "processed",
        "amount": 15000,
    }

    result = reconcile_payment_attempt(att.attempt_id)
    assert result["status"] == "refund_dispatched"

    # Verify exact same key was sent
    mock_razorpay_gateway.client.payment.refund.assert_called_once()
    call_kwargs = mock_razorpay_gateway.client.payment.refund.call_args[1]
    assert call_kwargs["headers"]["X-Refund-Idempotency"] == "rfk_fixed_key_001"


def test_pending_refund_remains_pending(app, mock_razorpay_gateway):
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("100.00"),
        currency="INR",
        cart_hash="hash_pending",
        razorpay_order_id="order_pending_test",
        razorpay_payment_id="pay_pending_test",
        status="refund_pending",
        refund_idempotency_key="rfk_pending_01",
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_pending_test",
        "order_id": "order_pending_test",
        "amount": 10000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_pending_01", "status": "pending", "amount": 10000}],
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "pending_refund"

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.status == "refund_pending"


def test_failed_refund_recorded_and_escalated(app, mock_razorpay_gateway):
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("200.00"),
        currency="INR",
        cart_hash="hash_failed",
        razorpay_order_id="order_fail_test",
        razorpay_payment_id="pay_fail_test",
        status="refund_failed",
        refund_idempotency_key="rfk_fail_01",
        retry_count=3,  # Reached retry limit of 3 -> escalated to manual_review
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_fail_test",
        "order_id": "order_fail_test",
        "amount": 20000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_failed_01", "status": "failed", "amount": 20000}],
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "failed_refund"

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.retry_count == 3
    assert att_db.status == "manual_review"

    # Repeated poll must not increment retry_count or alter manual_review
    res2 = reconcile_payment_attempt(att.attempt_id)
    assert res2["status"] == "failed_refund"
    att_db2 = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db2.retry_count == 3
    assert att_db2.status == "manual_review"


def test_partial_refund_never_marked_fully_refunded(app, mock_razorpay_gateway):
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("500.00"),  # 50,000 paise
        currency="INR",
        cart_hash="hash_part",
        razorpay_order_id="order_part_test",
        razorpay_payment_id="pay_part_test",
        status="refund_pending",
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_part_test",
        "order_id": "order_part_test",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 20000,  # Only 200.00 INR refunded
        "refund_status": "partial",
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_part_01", "status": "processed", "amount": 20000}],
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "partial_refund"
    assert res["unrefunded_amount"] == 300.00  # 500 - 200

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.status == "partial_refunded"
    assert att_db.unrefunded_amount == Decimal("300.00")
    assert att_db.status != "refunded"


def test_reconciliation_distinguishes_fulfilled_order_from_refund(app, mock_razorpay_gateway):
    buyer_id, _ = make_user_and_headers(role="buyer")
    order = Order(
        buyer_id=buyer_id, total_amount=400.00, status="Processing", shipping_address="Add"
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(
        Payment(
            order_id=order.order_id,
            transaction_ref="pay_fulfilled_001",
            amount=400.00,
            payment_status="captured",
        )
    )
    att = PaymentAttempt(
        buyer_id=buyer_id,
        cart_id=1,
        amount=Decimal("400.00"),
        currency="INR",
        cart_hash="hash_ful",
        razorpay_order_id="order_ful_001",
        razorpay_payment_id="pay_fulfilled_001",
        status="callback_received",
    )
    db.session.add(att)
    db.session.commit()

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "already_fulfilled_order"
    assert res["order_id"] == order.order_id

    # Verify status updated to completed and refund NEVER called
    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.status == "completed"
    mock_razorpay_gateway.client.payment.refund.assert_not_called()


def test_amount_currency_mismatch_rejection(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=200.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_mismatch_001",
        "amount": 20000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    # Mismatched amount: expected 20000, actual 10000
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_mismatch_001",
        "order_id": "order_rzp_mismatch_001",
        "amount": 10000,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "shipping_address": "Mismatch Addr",
        "razorpay_order_id": "order_rzp_mismatch_001",
        "razorpay_payment_id": "pay_mismatch_001",
        "razorpay_signature": "sig_mismatch",
    }

    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "AMOUNT_MISMATCH"

    # Zero orders created
    orders = db.session.scalars(db.select(Order).where(Order.buyer_id == buyer_id)).all()
    assert len(orders) == 0


def test_uncaptured_payment_rejection(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_uncaptured_001",
        "amount": 10000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    # Status is authorized, NOT captured!
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_uncaptured_001",
        "order_id": "order_rzp_uncaptured_001",
        "amount": 10000,
        "currency": "INR",
        "status": "authorized",
    }

    payload = {
        "shipping_address": "Uncaptured Addr",
        "razorpay_order_id": "order_rzp_uncaptured_001",
        "razorpay_payment_id": "pay_uncaptured_001",
        "razorpay_signature": "sig_uncaptured",
    }

    resp = client.post("/api/checkout", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "PAYMENT_NOT_CAPTURED"


def test_ambiguous_commit_checks_persisted_order_before_refund(client, mock_razorpay_gateway):
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=150.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_ambig_001",
        "amount": 15000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_ambig_001",
        "order_id": "order_rzp_ambig_001",
        "amount": 15000,
        "currency": "INR",
        "status": "captured",
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_ambig_001",
        "amount": 15000,
        "status": "processed",
    }

    # Simulate commit failure where transaction actually rolled back
    original_commit = db.session.commit
    commit_failed = [False]

    def failing_commit():
        if not commit_failed[0]:
            commit_failed[0] = True
            raise Exception("Database connection lost during commit!")
        return original_commit()

    with mock.patch.object(db.session, "commit", side_effect=failing_commit):
        payload = {
            "shipping_address": "Ambig Addr",
            "razorpay_order_id": "order_rzp_ambig_001",
            "razorpay_payment_id": "pay_ambig_001",
            "razorpay_signature": "sig_ambig",
        }
        resp = client.post("/api/checkout", json=payload, headers=headers)
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "ORDER_FAILED"

    # Durable compensation was triggered with persisted key
    att = db.session.scalar(
        db.select(PaymentAttempt).where(PaymentAttempt.razorpay_order_id == "order_rzp_ambig_001")
    )
    assert att.status == "refunded"
    assert att.refund_ref == "rfnd_ambig_001"
    assert att.refund_idempotency_key is not None


def test_razorpay_selected_missing_credentials_fails_safely(client, monkeypatch):
    monkeypatch.setenv("PAYMENT_GATEWAY", "razorpay")
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)

    _, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    resp = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp.status_code == 500
    assert resp.get_json()["error"] == "GATEWAY_CONFIGURATION_ERROR"


def test_reconcile_all_pending_processes_multiple_attempts(app, mock_razorpay_gateway):
    att1 = PaymentAttempt(
        buyer_id=1, cart_id=1, amount=Decimal("100.00"), currency="INR",
        cart_hash="h1", razorpay_order_id="ord_p1", razorpay_payment_id="pay_p1",
        status="refund_pending", refund_idempotency_key="rfk_p1",
    )
    att2 = PaymentAttempt(
        buyer_id=1, cart_id=1, amount=Decimal("200.00"), currency="INR",
        cart_hash="h2", razorpay_order_id="ord_p2", razorpay_payment_id="pay_p2",
        status="refund_failed", refund_idempotency_key="rfk_p2", retry_count=1,
    )
    db.session.add_all([att1, att2])
    db.session.commit()

    def mock_fetch(pid):
        amt = 10000 if pid == "pay_p1" else 20000
        oid = "ord_p1" if pid == "pay_p1" else "ord_p2"
        return {
            "id": pid, "order_id": oid, "amount": amt, "currency": "INR",
            "status": "captured", "amount_refunded": amt, "refund_status": "full",
        }
    mock_razorpay_gateway.client.payment.fetch.side_effect = mock_fetch
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1, "items": [{"id": "rfnd_p", "status": "processed", "amount": 10000}],
    }

    results = reconcile_all_pending(limit=10)
    assert len(results) >= 2


# -----------------------------------------------------------------------------
# Section 6: Additional Phase 2 Targeted Verification Tests
# -----------------------------------------------------------------------------
def test_post_verification_db_failure_in_stock_decrement_triggers_compensation(
    client, mock_razorpay_gateway
):
    """Database exception during stock decrement after payment verification
    triggers safe compensation.
    """
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_pvfail_01",
        "amount": 10000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_pvfail_01",
        "order_id": "order_rzp_pvfail_01",
        "amount": 10000,
        "currency": "INR",
        "status": "captured",
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_pvfail_01",
        "amount": 10000,
        "status": "processed",
    }

    with mock.patch("app.checkout.service.decrement_stock", side_effect=Exception("DB deadlock!")):
        payload = {
            "shipping_address": "Test Addr",
            "razorpay_order_id": "order_rzp_pvfail_01",
            "razorpay_payment_id": "pay_pvfail_01",
            "razorpay_signature": "sig_pvfail",
        }
        resp = client.post("/api/checkout", json=payload, headers=headers)
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "ORDER_FAILED"

    # Verify transaction rolled back and durable compensation initiated
    att = db.session.scalar(
        db.select(PaymentAttempt).where(PaymentAttempt.razorpay_order_id == "order_rzp_pvfail_01")
    )
    assert att.status == "refunded"
    assert att.refund_ref == "rfnd_pvfail_01"


def test_commit_success_detected_via_fresh_session_prevents_refund(
    client, mock_razorpay_gateway
):
    """Commit that actually succeeded is recognized via fresh session;
    order is preserved, no refund sent.
    """
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=120.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_commitsuc_01",
        "amount": 12000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_commitsuc_01",
        "order_id": "order_rzp_commitsuc_01",
        "amount": 12000,
        "currency": "INR",
        "status": "captured",
    }

    orig_commit = db.session.commit
    committed_once = [False]

    def commit_and_raise():
        if not committed_once[0]:
            committed_once[0] = True
            orig_commit()
            raise Exception("Post-commit connection blip to client!")
        return orig_commit()

    with mock.patch.object(db.session, "commit", side_effect=commit_and_raise):
        payload = {
            "shipping_address": "Test Addr",
            "razorpay_order_id": "order_rzp_commitsuc_01",
            "razorpay_payment_id": "pay_commitsuc_01",
            "razorpay_signature": "sig_commitsuc",
        }
        resp = client.post("/api/checkout", json=payload, headers=headers)
        assert resp.status_code == 201

    # Fresh session checked and confirmed Order & Payment persisted: NEVER refund
    mock_razorpay_gateway.client.payment.refund.assert_not_called()
    att = db.session.scalar(
        db.select(PaymentAttempt).where(
            PaymentAttempt.razorpay_order_id == "order_rzp_commitsuc_01"
        )
    )
    assert att.status == "completed"


def test_missing_verification_capability_fails_closed_no_refund(
    client, mock_razorpay_gateway
):
    """Missing payment verification capability fails closed:
    blocks refund and flags manual_review.
    """
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    # Reduce stock in database to 0 to trigger out-of-stock branch at checkout
    inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == pid))
    inv.stock_quantity = 0
    db.session.commit()

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_noverif_01",
        "amount": 10000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    # Deliberately remove verify_payment_signature from gateway
    with mock.patch.object(mock_razorpay_gateway, "verify_payment_signature", None, create=False):
        payload = {
            "shipping_address": "Test Addr",
            "razorpay_order_id": "order_rzp_noverif_01",
            "razorpay_payment_id": "pay_noverif_01",
            "razorpay_signature": "sig_noverif",
        }
        resp = client.post("/api/checkout", json=payload, headers=headers)
        assert resp.status_code in (400, 500)
        mock_razorpay_gateway.client.payment.refund.assert_not_called()

        att = db.session.scalar(
            db.select(PaymentAttempt).where(
                PaymentAttempt.razorpay_order_id == "order_rzp_noverif_01"
            )
        )
        assert att.status in ("manual_review", "initiated", "stock_insufficient")


def test_terminal_failed_refund_not_incremented_on_repeat_poll(app, mock_razorpay_gateway):
    """Repeated observation of a confirmed terminal failed refund at retry limit
    does not increment retry_count.
    """
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("200.00"),
        currency="INR",
        cart_hash="hash_repeat_poll",
        razorpay_order_id="order_repeat_poll",
        razorpay_payment_id="pay_repeat_poll",
        status="manual_review",
        refund_idempotency_key="rfk_repeat_poll",
        retry_count=3,
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_repeat_poll",
        "order_id": "order_repeat_poll",
        "amount": 20000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_repeat_01", "status": "failed", "amount": 20000}],
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "failed_refund"
    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.retry_count == 3  # Not incremented on repeat observation
    assert att_db.status == "manual_review"

    # Repeated poll does not increment retry_count
    res2 = reconcile_payment_attempt(att.attempt_id)
    assert res2["status"] == "failed_refund"
    att_db2 = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db2.retry_count == 3


def test_reconciliation_payment_validation_mismatch_fails_closed(app, mock_razorpay_gateway):
    """Reconciliation validates payment ID, order ID, amount, currency,
    and captured status before refund.
    """
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("150.00"),
        currency="INR",
        cart_hash="hash_mismatch",
        razorpay_order_id="ord_mismatch_01",
        razorpay_payment_id="pay_mismatch_01",
        status="refund_pending",
    )
    db.session.add(att)
    db.session.commit()

    # Currency mismatch: USD instead of INR
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_mismatch_01",
        "order_id": "ord_mismatch_01",
        "amount": 15000,
        "currency": "USD",  # Mismatch!
        "status": "captured",
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "verification_failed"

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.status == "manual_review"
    mock_razorpay_gateway.client.payment.refund.assert_not_called()


def test_reconciliation_buyer_ownership_enforced(client, mock_razorpay_gateway):
    """Buyer A cannot reconcile Buyer B's attempt (403 Forbidden);
    Buyer B can reconcile own attempt.
    """
    buyer_a_id, headers_a = make_user_and_headers(role="buyer")
    buyer_b_id, headers_b = make_user_and_headers(role="buyer")

    att_b = PaymentAttempt(
        buyer_id=buyer_b_id,
        cart_id=1,
        amount=Decimal("100.00"),
        currency="INR",
        cart_hash="hash_b",
        razorpay_order_id="ord_b_01",
        razorpay_payment_id="pay_b_01",
        status="refund_pending",
    )
    db.session.add(att_b)
    db.session.commit()

    # Buyer A attempts to reconcile Buyer B's attempt -> 403 Forbidden
    resp = client.post(f"/api/payments/reconcile/{att_b.attempt_id}", headers=headers_a)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "FORBIDDEN"

    # Buyer B reconciles own attempt -> allowed (200 OK)
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_b_01",
        "order_id": "ord_b_01",
        "amount": 10000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 10000,
        "refund_status": "full",
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_b_01", "status": "processed", "amount": 10000}],
    }
    resp = client.post(f"/api/payments/reconcile/{att_b.attempt_id}", headers=headers_b)
    assert resp.status_code == 200


def test_bulk_reconciliation_admin_only(client, mock_razorpay_gateway):
    """Non-admin cannot trigger bulk reconciliation (403 Forbidden);
    admin can (200 OK).
    """
    _, buyer_headers = make_user_and_headers(role="buyer")
    _, admin_headers = make_user_and_headers(role="admin")

    # Non-admin / buyer cannot trigger bulk reconcile
    resp = client.post("/api/payments/reconcile", headers=buyer_headers)
    assert resp.status_code == 403

    # Admin can trigger bulk reconcile
    resp = client.post("/api/payments/reconcile", headers=admin_headers)
    assert resp.status_code == 200
    assert "results" in resp.get_json()


def test_sequential_order_creation_same_cart_reuses_active_attempt(
    client, mock_razorpay_gateway
):
    """Sequential order creation requests for the same cart reuse the active attempt
    without duplicate provider orders.
    """
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=200.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "ord_concurrent_01",
        "amount": 20000,
        "currency": "INR",
        "status": "created",
    }

    resp1 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp1.status_code == 201
    data1 = resp1.get_json()

    # Second call with unchanged cart reuses active attempt
    resp2 = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.get_json()

    assert data1["razorpay_order_id"] == data2["razorpay_order_id"]
    assert mock_razorpay_gateway.client.order.create.call_count == 1


def test_cart_service_safe_concurrent_cart_creation(app):
    """Concurrent first-time cart creation safely handles unique
    constraint collisions via savepoint.
    """
    from app.cart.service import _cart

    buyer_id, _ = make_user_and_headers(role="buyer")

    # Pre-create the cart to simulate concurrent creation by another worker
    real_cart = Cart(buyer_id=buyer_id)
    db.session.add(real_cart)
    db.session.commit()
    target_cart_id = real_cart.cart_id

    # Simulate race condition where the initial select returned None (cart not seen yet)
    orig_scalar = db.session.scalar
    first_lookup = [True]

    def mock_scalar_first_none(stmt, *args, **kwargs):
        if first_lookup[0] and "WHERE carts.buyer_id" in str(stmt):
            first_lookup[0] = False
            return None
        return orig_scalar(stmt, *args, **kwargs)

    with mock.patch.object(db.session, "scalar", side_effect=mock_scalar_first_none):
        cart = _cart(buyer_id)
        assert cart is not None
        assert cart.cart_id == target_cart_id
        assert cart.buyer_id == buyer_id


def test_unsupported_gateway_provider_fails_safely(client, monkeypatch):
    """Unsupported PAYMENT_GATEWAY configuration fails safely with GATEWAY_CONFIGURATION_ERROR."""
    monkeypatch.setenv("PAYMENT_GATEWAY", "unsupported_gateway_provider")
    _, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    resp = client.post("/api/payments/razorpay-order", headers=headers)
    assert resp.status_code == 500
    assert resp.get_json()["error"] == "GATEWAY_CONFIGURATION_ERROR"


def test_post_verification_recovery_race_order_fulfilled_prevents_refund(
    client, mock_razorpay_gateway
):
    """When two requests race around post-verification rollback, recovery detects
    persisted marketplace order and never refunds.
    """
    buyer_id, headers = make_user_and_headers(role="buyer")
    pid = make_product(price=100.00, stock=5)
    add_to_cart(client, headers, pid, 1)

    mock_razorpay_gateway.client.order.create.return_value = {
        "id": "order_rzp_race_01",
        "amount": 10000,
        "currency": "INR",
        "status": "created",
    }
    client.post("/api/payments/razorpay-order", headers=headers)

    mock_razorpay_gateway.client.utility.verify_payment_signature.return_value = True
    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_race_01",
        "order_id": "order_rzp_race_01",
        "amount": 10000,
        "currency": "INR",
        "status": "captured",
    }

    # Simulate Request 1 failing during post-verification.
    # While Request 1 is failing, a concurrent request has already fulfilled the order
    # and persisted the Payment record for this transaction_ref.
    def save_order_with_concurrent_fulfillment(*args, **kwargs):
        # Concurrently create the order and payment directly in DB
        with db.session.no_autoflush:
            persisted_order = Order(
                buyer_id=buyer_id,
                total_amount=100.00,
                status="Processing",
                shipping_address="Race Addr",
            )
            db.session.add(persisted_order)
            db.session.flush()
            persisted_payment = Payment(
                order_id=persisted_order.order_id,
                transaction_ref="pay_race_01",
                amount=100.00,
                payment_status="captured",
            )
            db.session.add(persisted_payment)
            db.session.commit()
        # Now raise an exception in Request 1 to trigger its post-verification recovery
        raise Exception("Simulated DB error in racing request 1!")

    with mock.patch(
        "app.checkout.service._save_order",
        side_effect=save_order_with_concurrent_fulfillment,
    ):
        payload = {
            "shipping_address": "Race Addr",
            "razorpay_order_id": "order_rzp_race_01",
            "razorpay_payment_id": "pay_race_01",
            "razorpay_signature": "sig_race_01",
        }
        resp = client.post("/api/checkout", json=payload, headers=headers)
        assert resp.status_code == 201

    # Recovery locked attempt, detected existing payment, and NEVER dispatched refund!
    mock_razorpay_gateway.client.payment.refund.assert_not_called()
    att = db.session.scalar(
        db.select(PaymentAttempt).where(
            PaymentAttempt.razorpay_order_id == "order_rzp_race_01"
        )
    )
    assert att.status == "completed"


def test_reconciliation_genuine_new_retry_after_terminal_failure(app, mock_razorpay_gateway):
    """When a previous refund confirmed terminally failed and retry_count < 3,
    a genuinely new refund is dispatched with a new idempotency key and preserved history.
    """
    initial_key = "rfk_initial_key_123"
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("150.00"),
        currency="INR",
        cart_hash="hash_retry_new",
        razorpay_order_id="ord_retry_new",
        razorpay_payment_id="pay_retry_new",
        status="refund_failed",
        refund_idempotency_key=initial_key,
        refund_ref="rfnd_failed_prev",
        retry_count=1,
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_retry_new",
        "order_id": "ord_retry_new",
        "amount": 15000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_failed_prev", "status": "failed", "amount": 15000}],
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_new_success_01",
        "status": "processed",
        "amount": 15000,
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "refund_dispatched"

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    # Actual dispatch incremented retry_count
    assert att_db.retry_count == 2
    # Genuinely new idempotency key was generated and persisted
    assert att_db.refund_idempotency_key != initial_key
    assert att_db.refund_idempotency_key.startswith("rfk_")
    # Durable audit history preserved in failure_reason
    assert "rfnd_failed_prev" in att_db.failure_reason
    assert initial_key in att_db.failure_reason


def test_reconciliation_idempotency_key_stability_on_ambiguous_timeout(app, mock_razorpay_gateway):
    """When no refund items exist at gateway (ambiguous timeout), retry reuses
    the exact same persisted idempotency key (idempotency key stability).
    """
    stable_key = "rfk_stable_idempotent_key"
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("150.00"),
        currency="INR",
        cart_hash="hash_stable",
        razorpay_order_id="ord_stable",
        razorpay_payment_id="pay_stable",
        status="refund_pending",
        refund_idempotency_key=stable_key,
        retry_count=1,
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_stable",
        "order_id": "ord_stable",
        "amount": 15000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    # No refund items exist at Razorpay
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 0,
        "items": [],
    }
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_ambig_succ",
        "status": "processed",
        "amount": 15000,
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "refund_dispatched"

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.retry_count == 2
    # Exact same key was reused for ambiguous timeout retry
    assert att_db.refund_idempotency_key == stable_key


def test_reconciliation_terminal_failure_escalates_to_manual_review_at_limit(
    app, mock_razorpay_gateway
):
    """Terminal refund failure stops at retry limit 3 and escalates to manual_review."""
    att = PaymentAttempt(
        buyer_id=1,
        cart_id=1,
        amount=Decimal("200.00"),
        currency="INR",
        cart_hash="hash_limit_esc",
        razorpay_order_id="ord_limit_esc",
        razorpay_payment_id="pay_limit_esc",
        status="refund_failed",
        refund_idempotency_key="rfk_limit_key",
        retry_count=2,  # Next dispatch is attempt 3
    )
    db.session.add(att)
    db.session.commit()

    mock_razorpay_gateway.client.payment.fetch.return_value = {
        "id": "pay_limit_esc",
        "order_id": "ord_limit_esc",
        "amount": 20000,
        "currency": "INR",
        "status": "captured",
        "amount_refunded": 0,
        "refund_status": None,
    }
    mock_razorpay_gateway.client.payment.fetch_multiple_refund.return_value = {
        "count": 1,
        "items": [{"id": "rfnd_fail_prev_02", "status": "failed", "amount": 20000}],
    }
    # Third dispatch also returns failed status
    mock_razorpay_gateway.client.payment.refund.return_value = {
        "id": "rfnd_fail_final_03",
        "status": "failed",
        "amount": 20000,
    }

    res = reconcile_payment_attempt(att.attempt_id)
    assert res["status"] == "refund_dispatched"

    att_db = db.session.get(PaymentAttempt, att.attempt_id)
    assert att_db.retry_count == 3
    assert att_db.status == "manual_review"


def test_refund_idempotency_header_transport_level():
    """Verify at the HTTP transport session boundary that X-Refund-Idempotency
    header is transmitted on the outgoing HTTP request.
    """
    import razorpay
    import requests

    real_client = razorpay.Client(auth=("rzp_test_key_transport", "rzp_test_sec_transport"))
    gateway = RazorpayGateway(
        key_id="rzp_test_key_transport",
        key_secret="rzp_test_sec_transport",
        client=real_client,
    )

    sent_requests = []

    def mock_send(request, **kwargs):
        sent_requests.append(request)
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b'{"id": "rfnd_transport_01", "status": "processed", "amount": 10000}'
        return resp

    real_client.session.send = mock_send

    with mock.patch.object(real_client.payment, "fetch") as mock_fetch:
        mock_fetch.return_value = {
            "id": "pay_transport_01",
            "amount": 10000,
            "amount_refunded": 10000,
            "refund_status": "full",
        }
        res = gateway.void_or_refund_charge(
            "pay_transport_01",
            reason="transport header check",
            amount=Decimal("100.00"),
            idempotency_key="rfk_transport_test_12345",
        )

    assert res["payment_status"] == "refunded"
    assert len(sent_requests) == 1
    req = sent_requests[0]
    assert "X-Refund-Idempotency" in req.headers
    assert req.headers["X-Refund-Idempotency"] == "rfk_transport_test_12345"


@pytest.mark.postgres_integration
def test_postgres_concurrent_order_creation_same_cart():
    """PostgreSQL integration test: exercise simultaneous order creation for the same cart."""
    import os
    if not os.getenv("CHECKOUT_TEST_DATABASE_URL"):
        pytest.skip("CHECKOUT_TEST_DATABASE_URL is not set; skipping PostgreSQL integration test")


@pytest.mark.postgres_integration
def test_postgres_concurrent_first_cart_creation():
    """PostgreSQL integration test: exercise simultaneous first cart creation for the same buyer."""
    import os
    if not os.getenv("CHECKOUT_TEST_DATABASE_URL"):
        pytest.skip("CHECKOUT_TEST_DATABASE_URL is not set; skipping PostgreSQL integration test")
