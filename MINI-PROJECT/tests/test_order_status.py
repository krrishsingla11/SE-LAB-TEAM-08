"""Tests for Artisan Order Status Updates (SE8-32 / OMH-F-013 / SAD §4.4 / STP TC-ORD-02).

Covers:
- Successful order status transitions:
    Pending -> Processing -> Shipped -> Delivered.
- Buyer order history reflection (GET /api/orders).
- Artisan incoming-orders dashboard endpoint (GET /api/seller/orders).
- Invalid state transitions (skipped states, backward, same-state, out of Delivered).
- Malformed, missing, null, numeric, empty, and unknown statuses.
- Authorization and RBAC (unauthenticated, buyer role, cross-artisan forbidden, 404s).
- Multi-artisan order privacy and shared order-level status management.
- Transaction rollback and concurrency safety.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import uuid

from flask_jwt_extended import create_access_token
import pytest

from app.checkout.order_status import transition_order_status
from app.extensions import db
from app.models import Artisan, Category, Inventory, Order, OrderItem, Product, User

PASSWORD = "StrongP@ss123"
ADDRESS = "12 MG Road, Bengaluru 560001"


# ---------------------------------------------------------------- helpers
def _create_buyer(client, name="Test Buyer"):
    tag = uuid.uuid4().hex[:8]
    email = f"buyer_{tag}@pes.edu"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name, "role": "buyer"},
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.get_json()
    token = login.get_json()["token"]
    user = db.session.scalar(db.select(User).where(User.email == email))
    return {"Authorization": f"Bearer {token}"}, user.user_id


def _create_artisan(name="Test Artisan", shop_name="Artisan Crafts"):
    tag = uuid.uuid4().hex[:8]
    user = User(
        email=f"artisan_{tag}@pes.edu",
        password_hash="mock-hash",
        full_name=name,
        role="artisan",
    )
    db.session.add(user)
    db.session.flush()

    artisan = Artisan(
        user_id=user.user_id,
        shop_name=f"{shop_name} {tag}",
        bio="Master artisan of handcrafted goods.",
    )
    db.session.add(artisan)
    db.session.commit()

    token = create_access_token(
        identity=str(user.user_id),
        additional_claims={"role": "artisan"},
    )
    headers = {"Authorization": f"Bearer {token}"}
    return headers, user.user_id, artisan.artisan_id


def _create_product(artisan_id, title="Handmade Pottery", price=500.0, stock=20):
    tag = uuid.uuid4().hex[:8]
    category = Category(name=f"Crafts {tag}", slug=f"crafts-{tag}")
    db.session.add(category)
    db.session.flush()

    product = Product(
        artisan_id=artisan_id,
        category_id=category.category_id,
        title=title,
        description=f"Authentic handcrafted {title}",
        price=price,
        is_active=True,
    )
    db.session.add(product)
    db.session.flush()

    db.session.add(
        Inventory(
            product_id=product.product_id,
            stock_quantity=stock,
            low_stock_threshold=5,
        )
    )
    db.session.commit()
    return product.product_id


def _place_order(client, buyer_headers, cart_items):
    """Add items to cart and execute checkout. cart_items is list of (product_id, qty)."""
    for prod_id, qty in cart_items:
        res = client.post(
            "/api/cart/items",
            json={"product_id": prod_id, "quantity": qty},
            headers=buyer_headers,
        )
        assert res.status_code == 200, res.get_json()

    checkout_res = client.post(
        "/api/checkout",
        json={"shipping_address": ADDRESS, "payment_token": "tok_visa_success"},
        headers=buyer_headers,
    )
    assert checkout_res.status_code == 201, checkout_res.get_json()
    body = checkout_res.get_json()
    order_id = int(body["invoice_url"].strip("/").split("/")[2])
    return order_id, body


# ------------------------------------------------ Successful operations
def test_order_lifecycle_processing_to_shipped_to_delivered(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Ceramic Vase", 450.0, 10)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Initial order status from checkout is Processing
    order = db.session.get(Order, order_id)
    assert order.status == "Processing"

    # Step 1: Processing -> Shipped
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Shipped"},
        headers=artisan_headers,
    )
    assert res.status_code == 200, res.get_json()
    assert res.get_json() == {"order_id": order_id, "status": "Shipped"}

    db.session.expire_all()
    order = db.session.get(Order, order_id)
    assert order.status == "Shipped"

    # Step 2: Shipped -> Delivered
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Delivered"},
        headers=artisan_headers,
    )
    assert res.status_code == 200, res.get_json()
    assert res.get_json() == {"order_id": order_id, "status": "Delivered"}

    db.session.expire_all()
    order = db.session.get(Order, order_id)
    assert order.status == "Delivered"


def test_order_lifecycle_pending_to_processing(client):
    buyer_headers, buyer_id = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Brass Diya", 300.0, 10)

    # Create an order directly in Pending state (e.g., cash on delivery or pending payment)
    order = Order(
        buyer_id=buyer_id,
        total_amount=Decimal("300.00"),
        status="Pending",
        shipping_address=ADDRESS,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(
        OrderItem(order_id=order.order_id, product_id=prod_id, quantity=1, unit_price=300.0)
    )
    db.session.commit()

    res = client.put(
        f"/api/orders/{order.order_id}/status",
        json={"status": "Processing"},
        headers=artisan_headers,
    )
    assert res.status_code == 200, res.get_json()
    assert res.get_json() == {"order_id": order.order_id, "status": "Processing"}

    db.session.expire_all()
    reloaded = db.session.get(Order, order.order_id)
    assert reloaded.status == "Processing"


def test_buyer_sees_updated_status_in_order_history(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Silk Scarf", 750.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Initially buyer sees Processing
    history = client.get("/api/orders", headers=buyer_headers)
    assert history.status_code == 200
    orders = history.get_json()["orders"]
    matching = next(o for o in orders if o["order_id"] == order_id)
    assert matching["status"] == "Processing"

    # Artisan moves to Shipped
    client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Shipped"},
        headers=artisan_headers,
    )
    history = client.get("/api/orders", headers=buyer_headers)
    orders = history.get_json()["orders"]
    matching = next(o for o in orders if o["order_id"] == order_id)
    assert matching["status"] == "Shipped"

    # Artisan moves to Delivered
    client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Delivered"},
        headers=artisan_headers,
    )
    history = client.get("/api/orders", headers=buyer_headers)
    orders = history.get_json()["orders"]
    matching = next(o for o in orders if o["order_id"] == order_id)
    assert matching["status"] == "Delivered"


def test_artisan_dashboard_receives_expected_seller_orders_response(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan(shop_name="Pottery Works")
    p1 = _create_product(artisan_id, "Clay Bowl", 200.0, 10)
    p2 = _create_product(artisan_id, "Clay Pitcher", 400.0, 10)

    order_id, _ = _place_order(client, buyer_headers, [(p1, 2), (p2, 1)])

    resp = client.get("/api/seller/orders", headers=artisan_headers)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert "orders" in data
    assert len(data["orders"]) >= 1

    card = next(o for o in data["orders"] if o["order_id"] == order_id)
    assert card["order_id"] == order_id
    assert card["status"] == "Processing"
    assert card["shipping_address"] == ADDRESS
    assert card["total"] == 800.0  # 2*200 + 1*400
    assert card["created_at"] is not None
    assert len(card["items"]) == 2

    # Check items match requirements of dashboard.html
    items_by_id = {i["product_id"]: i for i in card["items"]}
    assert items_by_id[p1]["title"] == "Clay Bowl"
    assert items_by_id[p1]["quantity"] == 2
    assert items_by_id[p1]["unit_price"] == 200.0
    assert items_by_id[p2]["title"] == "Clay Pitcher"
    assert items_by_id[p2]["quantity"] == 1
    assert items_by_id[p2]["unit_price"] == 400.0


# ------------------------------------------------ Invalid transitions
def test_invalid_transition_processing_to_delivered(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Handmade Rug", 1200.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Skipping Shipped is rejected
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Delivered"},
        headers=artisan_headers,
    )
    assert res.status_code == 400, res.get_json()
    err = res.get_json()
    assert err["error"] == "INVALID_TRANSITION"

    order = db.session.get(Order, order_id)
    assert order.status == "Processing"


def test_invalid_transition_shipped_to_processing(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Wood Carving", 650.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Move to Shipped first
    client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Shipped"},
        headers=artisan_headers,
    )

    # Backward transition is rejected
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Processing"},
        headers=artisan_headers,
    )
    assert res.status_code == 400, res.get_json()
    err = res.get_json()
    assert err["error"] == "INVALID_TRANSITION"

    order = db.session.get(Order, order_id)
    assert order.status == "Shipped"


def test_invalid_transition_delivered_to_shipped(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Painted Plate", 350.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Advance to Delivered
    client.put(
        f"/api/orders/{order_id}/status", json={"status": "Shipped"}, headers=artisan_headers
    )
    client.put(
        f"/api/orders/{order_id}/status", json={"status": "Delivered"}, headers=artisan_headers
    )

    # Any transition out of Delivered is rejected
    for target in ("Shipped", "Processing", "Pending"):
        res = client.put(
            f"/api/orders/{order_id}/status",
            json={"status": target},
            headers=artisan_headers,
        )
        assert res.status_code == 400, res.get_json()
        assert res.get_json()["error"] == "INVALID_TRANSITION"

    order = db.session.get(Order, order_id)
    assert order.status == "Delivered"


def test_same_state_transition_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Ceramic Mug", 250.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Same state Processing -> Processing is rejected
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Processing"},
        headers=artisan_headers,
    )
    assert res.status_code == 400, res.get_json()
    assert res.get_json()["error"] == "INVALID_TRANSITION"


def test_unknown_status_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Incense Stand", 150.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    for bad in ("Cancelled", "Refunded", "shipped", "COMPLETE", "Unknown"):
        res = client.put(
            f"/api/orders/{order_id}/status",
            json={"status": bad},
            headers=artisan_headers,
        )
        assert res.status_code == 400, res.get_json()
        assert res.get_json()["error"] == "INVALID_STATUS"


def test_missing_status_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Stone Idol", 900.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    res = client.put(
        f"/api/orders/{order_id}/status",
        json={},
        headers=artisan_headers,
    )
    assert res.status_code == 400, res.get_json()
    assert res.get_json()["error"] == "MISSING_STATUS"


def test_null_status_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Copper Vessel", 1100.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": None},
        headers=artisan_headers,
    )
    assert res.status_code == 400, res.get_json()
    assert res.get_json()["error"] == "INVALID_STATUS"


def test_numeric_status_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Jute Bag", 180.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    for val in (123, 1.5, True):
        res = client.put(
            f"/api/orders/{order_id}/status",
            json={"status": val},
            headers=artisan_headers,
        )
        assert res.status_code == 400, res.get_json()
        assert res.get_json()["error"] == "INVALID_STATUS"


def test_empty_status_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Bamboo Flute", 220.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    for empty in ("", "   "):
        res = client.put(
            f"/api/orders/{order_id}/status",
            json={"status": empty},
            headers=artisan_headers,
        )
        assert res.status_code == 400, res.get_json()
        assert res.get_json()["error"] == "INVALID_STATUS"


def test_malformed_request_body_rejected(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Terracotta Bowl", 300.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Non-dictionary JSON or raw string
    res = client.put(
        f"/api/orders/{order_id}/status",
        data="just a plain string",
        content_type="text/plain",
        headers=artisan_headers,
    )
    assert res.status_code == 400, res.get_json()
    assert res.get_json()["error"] == "INVALID_INPUT"


# ------------------------------------------------ Authorization & RBAC
def test_unauthenticated_request_rejected(client):
    res = client.put("/api/orders/1/status", json={"status": "Shipped"})
    assert res.status_code == 401, res.get_json()

    res_get = client.get("/api/seller/orders")
    assert res_get.status_code == 401, res_get.get_json()


def test_buyer_role_forbidden_from_updating_status(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Glass Figurine", 600.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    # Buyer attempting PUT /api/orders/<id>/status
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Shipped"},
        headers=buyer_headers,
    )
    assert res.status_code == 403, res.get_json()
    assert res.get_json()["error"] == "FORBIDDEN"

    # Buyer attempting GET /api/seller/orders
    res = client.get("/api/seller/orders", headers=buyer_headers)
    assert res.status_code == 403, res.get_json()
    assert res.get_json()["error"] == "FORBIDDEN"


def test_artisan_cannot_update_unowned_order(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_a_headers, _, artisan_a_id = _create_artisan(name="Artisan A")
    artisan_b_headers, _, artisan_b_id = _create_artisan(name="Artisan B")

    # Order contains only Artisan B's product
    prod_b = _create_product(artisan_b_id, "Artisan B Craft", 500.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod_b, 1)])

    # Artisan A tries to advance Artisan B's order
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Shipped"},
        headers=artisan_a_headers,
    )
    assert res.status_code == 403, res.get_json()
    assert res.get_json()["error"] == "FORBIDDEN"

    # Verify status is unchanged
    order = db.session.get(Order, order_id)
    assert order.status == "Processing"


def test_nonexistent_order_returns_404(client):
    artisan_headers, _, _ = _create_artisan()
    res = client.put(
        "/api/orders/999999/status",
        json={"status": "Shipped"},
        headers=artisan_headers,
    )
    assert res.status_code == 404, res.get_json()
    assert res.get_json()["error"] == "ORDER_NOT_FOUND"


def test_seller_orders_does_not_expose_other_artisans_orders(client):
    buyer1_headers, _ = _create_buyer(client, name="Buyer 1")
    buyer2_headers, _ = _create_buyer(client, name="Buyer 2")

    artisan_a_headers, _, artisan_a_id = _create_artisan(name="Artisan Alpha")
    artisan_b_headers, _, artisan_b_id = _create_artisan(name="Artisan Beta")

    prod_a = _create_product(artisan_a_id, "Alpha Craft", 300.0, 10)
    prod_b = _create_product(artisan_b_id, "Beta Craft", 600.0, 10)

    order_a_id, _ = _place_order(client, buyer1_headers, [(prod_a, 1)])
    order_b_id, _ = _place_order(client, buyer2_headers, [(prod_b, 1)])

    # Artisan A's dashboard
    resp_a = client.get("/api/seller/orders", headers=artisan_a_headers)
    orders_a = [o["order_id"] for o in resp_a.get_json()["orders"]]
    assert order_a_id in orders_a
    assert order_b_id not in orders_a

    # Artisan B's dashboard
    resp_b = client.get("/api/seller/orders", headers=artisan_b_headers)
    orders_b = [o["order_id"] for o in resp_b.get_json()["orders"]]
    assert order_b_id in orders_b
    assert order_a_id not in orders_b


def test_multi_artisan_order_privacy_and_access(client):
    """When an order has items from multiple artisans:
    - Each artisan only sees their own items and subtotal in GET /api/seller/orders.
    - Both artisans have authorization to manage the shared order-level status.
    """
    buyer_headers, _ = _create_buyer(client, name="Multi Buyer")
    artisan_a_headers, _, artisan_a_id = _create_artisan(name="Artisan 1")
    artisan_b_headers, _, artisan_b_id = _create_artisan(name="Artisan 2")

    prod_a = _create_product(artisan_a_id, "Item 1", 200.0, 5)
    prod_b = _create_product(artisan_b_id, "Item 2", 300.0, 5)

    order_id, _ = _place_order(client, buyer_headers, [(prod_a, 2), (prod_b, 1)])

    # Artisan 1 views seller orders: only sees Item 1, total is 400.0
    resp1 = client.get("/api/seller/orders", headers=artisan_a_headers)
    card1 = next(o for o in resp1.get_json()["orders"] if o["order_id"] == order_id)
    assert card1["total"] == 400.0
    assert len(card1["items"]) == 1
    assert card1["items"][0]["title"] == "Item 1"

    # Artisan 2 views seller orders: only sees Item 2, total is 300.0
    resp2 = client.get("/api/seller/orders", headers=artisan_b_headers)
    card2 = next(o for o in resp2.get_json()["orders"] if o["order_id"] == order_id)
    assert card2["total"] == 300.0
    assert len(card2["items"]) == 1
    assert card2["items"][0]["title"] == "Item 2"

    # Artisan 1 updates status to Shipped
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Shipped"},
        headers=artisan_a_headers,
    )
    assert res.status_code == 200

    # Artisan 2 can also update shared order status (e.g. to Delivered)
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Delivered"},
        headers=artisan_b_headers,
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "Delivered"


def test_multiple_items_same_artisan_no_duplicate_orders(client):
    """When an order has multiple items from the same artisan,
    GET /api/seller/orders must return the order only once.
    """
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    p1 = _create_product(artisan_id, "Product Alpha", 100.0, 10)
    p2 = _create_product(artisan_id, "Product Beta", 200.0, 10)

    order_id, _ = _place_order(client, buyer_headers, [(p1, 1), (p2, 2)])

    resp = client.get("/api/seller/orders", headers=artisan_headers)
    order_ids = [o["order_id"] for o in resp.get_json()["orders"]]
    assert order_ids.count(order_id) == 1


# ------------------------------------------------ Transaction & Concurrency
def test_invalid_update_leaves_persisted_status_unchanged(client):
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, _, artisan_id = _create_artisan()
    prod = _create_product(artisan_id, "Stable Item", 250.0, 5)
    order_id, _ = _place_order(client, buyer_headers, [(prod, 1)])

    # Initial status
    assert db.session.get(Order, order_id).status == "Processing"

    # Attempt bad transition
    res = client.put(
        f"/api/orders/{order_id}/status",
        json={"status": "Delivered"},
        headers=artisan_headers,
    )
    assert res.status_code == 400

    # Ensure status in DB was not modified
    db.session.expire_all()
    assert db.session.get(Order, order_id).status == "Processing"


def test_failed_update_rolls_back_safely(app, monkeypatch):
    """Ensure that if an error occurs during commit, rollback is called."""
    with app.app_context():
        _, user_id, artisan_id = _create_artisan()
        prod_id = _create_product(artisan_id, "Rollback Test", 100.0, 5)

        order = Order(
            buyer_id=user_id,
            total_amount=Decimal("100.00"),
            status="Processing",
            shipping_address=ADDRESS,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(
            OrderItem(order_id=order.order_id, product_id=prod_id, quantity=1, unit_price=100.0)
        )
        db.session.commit()

        def mock_commit():
            raise RuntimeError("Database connection severed during commit")

        monkeypatch.setattr(db.session, "commit", mock_commit)

        with pytest.raises(RuntimeError):
            transition_order_status(order.order_id, "Shipped", user_id)

        db.session.expire_all()
        assert db.session.get(Order, order.order_id).status == "Processing"


def test_concurrent_updates_cannot_bypass_state_machine(app, client):
    """Two concurrent requests attempting to advance the same order simultaneously.
    One must succeed (Processing -> Shipped), the second must fail with 400 (same state).
    """
    buyer_headers, _ = _create_buyer(client)
    artisan_headers, user_id, artisan_id = _create_artisan()
    prod_id = _create_product(artisan_id, "Race Item", 300.0, 10)
    order_id, _ = _place_order(client, buyer_headers, [(prod_id, 1)])

    def _attempt_transition():
        with app.app_context():
            local_client = app.test_client()
            return local_client.put(
                f"/api/orders/{order_id}/status",
                json={"status": "Shipped"},
                headers=artisan_headers,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(_attempt_transition)
        f2 = executor.submit(_attempt_transition)
        r1 = f1.result()
        r2 = f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 400]

    with app.app_context():
        final_order = db.session.get(Order, order_id)
        assert final_order.status == "Shipped"
