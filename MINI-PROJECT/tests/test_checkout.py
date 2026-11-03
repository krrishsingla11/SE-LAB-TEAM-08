"""Checkout, atomic stock-lock, rollback & PostgreSQL concurrency tests (SE8-29 / F-015).

Covers:
- Successful checkout (auth, HTTP 201, Order/OrderItem/Payment persistence, stock decrement,
  cart clearing) - OMH-F-010, OMH-F-012, OMH-F-015
- Insufficient stock at checkout (HTTP 400, stock unchanged, zero orders/payments, no charge)
- Payment decline at checkout (HTTP 402, transaction rollback, stock & cart unchanged)
- Database commit failure after payment capture (HTTP 500, transaction rollback, deterministic
  compensating refund invoked once)
- Safe CHECKOUT_TEST_DATABASE_URL validation guardrails
- TC-INV-01: Concurrent checkout for the last remaining unit against real PostgreSQL
  row-level locking (SELECT ... FOR UPDATE)
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
import threading
import uuid

from flask_jwt_extended import create_access_token
import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import create_app
from app.extensions import db
from app.models import (
    Artisan,
    Cart,
    CartItem,
    Category,
    Inventory,
    Invoice,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductImage,
    User,
)
from app.payment import service as payment_service_mod
from app.payment.gateway import PaymentError

PASSWORD = "StrongP@ss123"
CHECKOUT_URL = "/api/checkout"
REQUIRED_PG_DRIVER = "postgresql+psycopg2"
REQUIRED_PG_DATABASE = "marketplace_checkout_test"
LOCAL_PG_HOSTS = frozenset({"localhost", "127.0.0.1"})
LOCAL_PG_PORT = 5433
CI_PG_HOST = "test_db"
CI_PG_PORT = 5432
PG_LOCK_TIMEOUT_MS = 5000
PG_STATEMENT_TIMEOUT_MS = 20000
PG_CONNECT_ARGS = {
    "options": (
        f"-c lock_timeout={PG_LOCK_TIMEOUT_MS} "
        f"-c statement_timeout={PG_STATEMENT_TIMEOUT_MS}"
    ),
    "connect_timeout": 10,
}
BARRIER_TIMEOUT = 10
FUTURE_TIMEOUT = 30


class ThreadSafeRecordingGateway:
    """Deterministic, thread-safe mock gateway that records captures and refunds."""

    def __init__(self):
        self._lock = threading.Lock()
        self._seq = 0
        self._captured = {}
        self.captures = []
        self.refunds = []

    def capture_charge(self, amount, token, idem_key=None):
        with self._lock:
            if idem_key and idem_key in self._captured:
                return dict(self._captured[idem_key])
            if not isinstance(token, str) or not token:
                raise PaymentError("INVALID_TOKEN", "A payment token is required", 422)
            if token == "tok_charge_declined":
                raise PaymentError("CARD_DECLINED", "Card declined", 402)
            if token == "tok_timeout":
                raise PaymentError("GATEWAY_TIMEOUT", "Payment gateway timed out", 504)
            if not token.startswith("tok_"):
                raise PaymentError("INVALID_TOKEN", "Unknown payment token", 422)
            self._seq += 1
            result = {
                "transaction_ref": f"TXN-MOCK-{self._seq:06d}",
                "payment_status": "captured",
                "amount": amount,
            }
            if idem_key:
                self._captured[idem_key] = dict(result)
            self.captures.append(dict(result))
            return result

    def void_or_refund_charge(self, txn_ref, reason):
        with self._lock:
            entry = {
                "transaction_ref": txn_ref,
                "payment_status": "refunded",
                "reason": reason,
            }
            self.refunds.append(entry)
            return dict(entry)


@pytest.fixture
def deterministic_gateway(monkeypatch):
    gateway = ThreadSafeRecordingGateway()
    monkeypatch.setattr(payment_service_mod, "_gateway", gateway)
    return gateway


def _is_ci_environment(env=None):
    env = os.environ if env is None else env
    return str(env.get("CI", "")).strip().lower() == "true"


def validate_checkout_test_database_url(raw_url, app_database_url=None, ci=None):
    """Strictly validate CHECKOUT_TEST_DATABASE_URL so tests never touch dev/prod databases.

    Returns the validated URL string, or None when raw_url is unset/blank.
    Raises RuntimeError for any unsafe target. Messages never contain credentials or URLs.
    """
    if raw_url is None or not raw_url.strip():
        return None
    raw = raw_url.strip()
    ci = _is_ci_environment() if ci is None else ci

    try:
        parsed = make_url(raw)
    except Exception:
        # Do not chain/echo the parser error: it can embed the full URL and password.
        raise RuntimeError("Invalid CHECKOUT_TEST_DATABASE_URL: URL could not be parsed.") from None

    if parsed.drivername != REQUIRED_PG_DRIVER:
        raise RuntimeError(
            f"CHECKOUT_TEST_DATABASE_URL must use the '{REQUIRED_PG_DRIVER}' dialect."
        )
    if "#" in raw:
        raise RuntimeError("CHECKOUT_TEST_DATABASE_URL must not contain a fragment.")
    if "?" in raw or parsed.query:
        raise RuntimeError(
            "CHECKOUT_TEST_DATABASE_URL must not contain query parameters "
            "(libpq options such as host/dbname can override the target)."
        )
    if parsed.database != REQUIRED_PG_DATABASE:
        raise RuntimeError(
            f"CHECKOUT_TEST_DATABASE_URL database name must be exactly '{REQUIRED_PG_DATABASE}'."
        )
    if parsed.port is None:
        raise RuntimeError("CHECKOUT_TEST_DATABASE_URL must specify an explicit port.")

    host = (parsed.host or "").strip().lower()
    port = parsed.port
    local_ok = host in LOCAL_PG_HOSTS and port == LOCAL_PG_PORT
    ci_ok = ci and host == CI_PG_HOST and port == CI_PG_PORT
    if not (local_ok or ci_ok):
        raise RuntimeError(
            f"Refusing PostgreSQL endpoint '{host}:{port}' in CHECKOUT_TEST_DATABASE_URL; "
            f"allowed: localhost/127.0.0.1:{LOCAL_PG_PORT}, or {CI_PG_HOST}:{CI_PG_PORT} in CI."
        )

    env_db_url = app_database_url if app_database_url is not None else os.getenv("DATABASE_URL")
    if env_db_url and env_db_url.strip():
        try:
            dev_url = make_url(env_db_url.strip())
        except Exception:
            dev_url = None
        if dev_url is not None and dev_url.get_backend_name() == "postgresql":
            same_target = (
                (dev_url.host or "localhost").lower() == host
                and (dev_url.port or 5432) == port
                and (dev_url.database or "") == parsed.database
            )
            if same_target:
                raise RuntimeError(
                    "CHECKOUT_TEST_DATABASE_URL must not point to the same database "
                    "as DATABASE_URL."
                )

    return raw

# ------------------------------------------------------------------ SQLite helpers


def _register_and_login_buyer(client):
    email = f"chk_buyer_{uuid.uuid4().hex[:8]}@pes.edu"
    reg = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Checkout Buyer",
            "role": "buyer",
        },
    )
    assert reg.status_code == 201, reg.get_json()
    user_id = reg.get_json()["user_id"]
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.get_json()
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    return user_id, headers


def _make_user_and_headers(role="buyer"):
    tag = uuid.uuid4().hex[:10]
    user = User(
        email=f"user_{tag}@pes.edu",
        password_hash="test-hash-not-used-for-direct-jwt",
        full_name=f"Test {role.title()} {tag}",
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    token = create_access_token(
        identity=str(user.user_id), additional_claims={"role": role}
    )
    return user.user_id, {"Authorization": f"Bearer {token}"}


def _make_product(title="Handcrafted Bowl", price=450.00, stock=5, is_active=True):
    tag = uuid.uuid4().hex[:10]
    seller = User(
        email=f"seller_{tag}@pes.edu",
        password_hash="test-hash",
        full_name="Artisan Seller",
        role="artisan",
    )
    db.session.add(seller)
    db.session.flush()
    artisan = Artisan(user_id=seller.user_id, shop_name=f"Studio {tag}")
    category = Category(name=f"Craft {tag}", slug=f"craft-{tag}")
    db.session.add_all([artisan, category])
    db.session.flush()
    product = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description=f"Authentic {title.lower()}",
        price=price,
        is_active=is_active,
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


def _add_to_cart(client, headers, product_id, quantity):
    resp = client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": quantity},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    return resp


# ----------------------------------------- Checkout integration tests (fast suite)
def test_checkout_requires_authentication_and_buyer_role(client):
    unauth = client.post(
        CHECKOUT_URL,
        json={"shipping_address": "12 MG Road, Bengaluru", "payment_token": "tok_visa_success"},
    )
    assert unauth.status_code == 401

    _, artisan_headers = _make_user_and_headers(role="artisan")
    forbidden = client.post(
        CHECKOUT_URL,
        json={"shipping_address": "12 MG Road, Bengaluru", "payment_token": "tok_visa_success"},
        headers=artisan_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.get_json()["error"] == "FORBIDDEN"


def test_checkout_rejects_empty_cart_and_invalid_address(client, deterministic_gateway):
    _, headers = _make_user_and_headers(role="buyer")

    bad_addr = client.post(
        CHECKOUT_URL,
        json={"shipping_address": "   ", "payment_token": "tok_visa_success"},
        headers=headers,
    )
    assert bad_addr.status_code == 422
    assert bad_addr.get_json()["error"] == "INVALID_ADDRESS"

    empty = client.post(
        CHECKOUT_URL,
        json={"shipping_address": "12 MG Road, Bengaluru", "payment_token": "tok_visa_success"},
        headers=headers,
    )
    assert empty.status_code == 400
    assert empty.get_json()["error"] == "CART_EMPTY"
    assert deterministic_gateway.captures == []


def test_checkout_inactive_product_aborts_without_charging(client, deterministic_gateway):
    buyer_id, headers = _make_user_and_headers(role="buyer")
    product_id = _make_product("Stoneware Mug", price=350.00, stock=3)
    _add_to_cart(client, headers, product_id, 1)

    product = db.session.get(Product, product_id)
    product.is_active = False
    db.session.commit()

    resp = client.post(
        CHECKOUT_URL,
        json={"shipping_address": "12 MG Road, Bengaluru", "payment_token": "tok_visa_success"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "PRODUCT_UNAVAILABLE"
    assert deterministic_gateway.captures == []
    inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == product_id))
    assert inv.stock_quantity == 3
    assert db.session.scalars(db.select(Order).where(Order.buyer_id == buyer_id)).all() == []


def test_checkout_success_persists_order_payment_decrements_stock_and_clears_cart(
    client, deterministic_gateway
):
    """OMH-F-010 / OMH-F-012 / OMH-F-015: Full positive buyer checkout flow."""
    buyer_id, headers = _register_and_login_buyer(client)
    vase_id = _make_product("Terracotta Vase", price=450.00, stock=5)
    scarf_id = _make_product("Handloom Scarf", price=300.00, stock=3)

    _add_to_cart(client, headers, vase_id, 2)
    _add_to_cart(client, headers, scarf_id, 1)

    resp = client.post(
        CHECKOUT_URL,
        json={
            "shipping_address": "42 Residency Road, Bengaluru 560025",
            "payment_token": "tok_visa_success",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["status"] == "Processing"
    assert body["payment_status"] == "captured"
    assert body["total"] == 1200.0
    assert body["transaction_ref"] == "TXN-MOCK-000001"
    assert body["invoice_url"] is None

    order = db.session.get(Order, body["order_id"])
    assert order is not None
    assert order.buyer_id == buyer_id
    assert order.status == "Processing"
    assert order.total_amount == Decimal("1200.00")
    assert order.shipping_address == "42 Residency Road, Bengaluru 560025"

    items = db.session.scalars(
        db.select(OrderItem)
        .where(OrderItem.order_id == order.order_id)
        .order_by(OrderItem.product_id)
    ).all()
    assert len(items) == 2
    by_prod = {item.product_id: (item.quantity, item.unit_price) for item in items}
    assert by_prod[vase_id] == (2, Decimal("450.00"))
    assert by_prod[scarf_id] == (1, Decimal("300.00"))

    payment = db.session.scalar(
        db.select(Payment).where(Payment.order_id == order.order_id)
    )
    assert payment is not None
    assert payment.payment_status == "captured"
    assert payment.amount == Decimal("1200.00")
    assert payment.transaction_ref == "TXN-MOCK-000001"

    vase_inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == vase_id))
    scarf_inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == scarf_id))
    assert vase_inv.stock_quantity == 3
    assert scarf_inv.stock_quantity == 2

    cart_after = client.get("/api/cart", headers=headers).get_json()
    assert cart_after == {"cart": [], "subtotal": 0.0}
    assert len(deterministic_gateway.captures) == 1
    assert deterministic_gateway.refunds == []


def test_checkout_insufficient_stock_returns_400_without_charging_or_partial_writes(
    client, deterministic_gateway
):
    """OMH-F-009 / OMH-F-015: Pre-payment lock rejects depleted stock and rolls back."""
    buyer_id, headers = _make_user_and_headers(role="buyer")
    available_id = _make_product("Brass Lamp", price=600.00, stock=4)
    depleted_id = _make_product("Carved Box", price=850.00, stock=2)

    _add_to_cart(client, headers, available_id, 1)
    _add_to_cart(client, headers, depleted_id, 2)

    # Stock drops after the buyer added the item to their cart.
    depleted_inv = db.session.scalar(
        db.select(Inventory).where(Inventory.product_id == depleted_id)
    )
    depleted_inv.stock_quantity = 1
    db.session.commit()

    resp = client.post(
        CHECKOUT_URL,
        json={
            "shipping_address": "10 Church Street, Bengaluru",
            "payment_token": "tok_visa_success",
        },
        headers=headers,
    )
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "INSUFFICIENT_STOCK"
    assert "Carved Box" in body["message"]
    assert "1 unit(s) available" in body["message"]

    # Neither product's stock changed, gateway was never called, no order/payment persisted.
    db.session.expire_all()
    avail_inv = db.session.scalar(
        db.select(Inventory).where(Inventory.product_id == available_id)
    )
    depl_inv = db.session.scalar(
        db.select(Inventory).where(Inventory.product_id == depleted_id)
    )
    assert avail_inv.stock_quantity == 4
    assert depl_inv.stock_quantity == 1

    orders = db.session.scalars(db.select(Order).where(Order.buyer_id == buyer_id)).all()
    payments = db.session.scalars(db.select(Payment)).all()
    assert orders == []
    assert payments == []
    assert deterministic_gateway.captures == []
    assert deterministic_gateway.refunds == []

    # Cart items remain intact so buyer can adjust quantities.
    cart_body = client.get("/api/cart", headers=headers).get_json()
    assert len(cart_body["cart"]) == 2


def test_checkout_payment_decline_returns_402_and_rolls_back_leaving_stock_intact(
    client, deterministic_gateway
):
    """OMH-F-010 / OMH-F-015: Declined payment rolls back transaction & preserves cart/stock."""
    buyer_id, headers = _make_user_and_headers(role="buyer")
    product_id = _make_product("Silver Anklet", price=1500.00, stock=2)
    _add_to_cart(client, headers, product_id, 2)

    declined = client.post(
        CHECKOUT_URL,
        json={
            "shipping_address": "88 Indiranagar, Bengaluru",
            "payment_token": "tok_charge_declined",
        },
        headers=headers,
    )
    assert declined.status_code == 402, declined.get_json()
    body = declined.get_json()
    assert body["error"] == "CARD_DECLINED"
    assert body["message"] == "Card declined"

    db.session.expire_all()
    inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == product_id))
    assert inv.stock_quantity == 2
    assert db.session.scalars(db.select(Order).where(Order.buyer_id == buyer_id)).all() == []
    assert db.session.scalars(db.select(OrderItem)).all() == []
    assert db.session.scalars(db.select(Payment)).all() == []
    assert deterministic_gateway.captures == []
    assert deterministic_gateway.refunds == []

    cart_body = client.get("/api/cart", headers=headers).get_json()
    assert len(cart_body["cart"]) == 1
    assert cart_body["cart"][0]["quantity"] == 2
    assert cart_body["subtotal"] == 3000.0

    # Subsequent retry with a valid token succeeds cleanly, proving lock/session recovery.
    retry = client.post(
        CHECKOUT_URL,
        json={
            "shipping_address": "88 Indiranagar, Bengaluru",
            "payment_token": "tok_visa_success",
        },
        headers=headers,
    )
    assert retry.status_code == 201, retry.get_json()
    db.session.expire_all()
    inv_after = db.session.scalar(db.select(Inventory).where(Inventory.product_id == product_id))
    assert inv_after.stock_quantity == 0


def test_checkout_commit_failure_after_payment_rolls_back_and_issues_compensating_refund(
    client, deterministic_gateway, monkeypatch
):
    """SAD 4.3.2 Step 6: Commit failure rolls back DB writes and refunds captured charge."""
    buyer_id, headers = _make_user_and_headers(role="buyer")
    product_id = _make_product("Embroidered Cushion", price=750.00, stock=4)
    _add_to_cart(client, headers, product_id, 2)

    commit_calls = {"count": 0, "captures_at_commit": None}

    def _failing_commit():
        commit_calls["count"] += 1
        commit_calls["captures_at_commit"] = len(deterministic_gateway.captures)
        raise OperationalError("COMMIT", {}, Exception("simulated database commit failure"))

    monkeypatch.setattr(db.session, "commit", _failing_commit)

    resp = client.post(
        CHECKOUT_URL,
        json={
            "shipping_address": "5 Jayanagar, Bengaluru",
            "payment_token": "tok_visa_success",
        },
        headers=headers,
    )
    assert resp.status_code == 500, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "ORDER_FAILED"

    # The intended commit ran exactly once, and only after payment was captured.
    assert commit_calls["count"] == 1
    assert commit_calls["captures_at_commit"] == 1

    # Uncommitted stock decrement, Order, OrderItem, Payment, and CartItem delete rolled back.
    db.session.expire_all()
    inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == product_id))
    assert inv.stock_quantity == 4
    assert db.session.scalars(db.select(Order).where(Order.buyer_id == buyer_id)).all() == []
    assert db.session.scalars(db.select(OrderItem)).all() == []
    assert db.session.scalars(db.select(Payment)).all() == []

    cart_items = db.session.scalars(
        db.select(CartItem).join(Cart).where(Cart.buyer_id == buyer_id)
    ).all()
    assert len(cart_items) == 1
    assert cart_items[0].quantity == 2

    # Payment was captured once and refunded once with the exact transaction reference.
    assert len(deterministic_gateway.captures) == 1
    captured_ref = deterministic_gateway.captures[0]["transaction_ref"]
    assert len(deterministic_gateway.refunds) == 1
    assert deterministic_gateway.refunds == [
        {
            "transaction_ref": captured_ref,
            "payment_status": "refunded",
            "reason": "order could not be saved",
        }
    ]


# ----------------------------------------- Safe PostgreSQL URL guard unit tests
def test_postgres_test_url_guard_rejects_unsafe_configurations():
    base = "postgresql+psycopg2://postgres:secretpw@127.0.0.1:5433/"
    good = base + "marketplace_checkout_test"
    assert validate_checkout_test_database_url(None) is None
    assert validate_checkout_test_database_url("   ") is None

    with pytest.raises(RuntimeError, match="dialect"):
        validate_checkout_test_database_url("sqlite:///:memory:")
    with pytest.raises(RuntimeError, match="dialect"):
        validate_checkout_test_database_url(good.replace("+psycopg2", ""))
    with pytest.raises(RuntimeError, match="database name"):
        validate_checkout_test_database_url(base + "marketplace")
    with pytest.raises(RuntimeError, match="fragment"):
        validate_checkout_test_database_url(good + "#frag")
    with pytest.raises(RuntimeError, match="explicit port"):
        validate_checkout_test_database_url(
            "postgresql+psycopg2://postgres:secretpw@127.0.0.1/marketplace_checkout_test"
        )
    with pytest.raises(RuntimeError, match="endpoint"):
        validate_checkout_test_database_url(
            "postgresql+psycopg2://postgres:secretpw@db:5432/marketplace_checkout_test"
        )
    with pytest.raises(RuntimeError, match="endpoint"):
        validate_checkout_test_database_url(good.replace("5433", "5432"))
    # test_db:5432 is only approved in CI.
    ci_url = "postgresql+psycopg2://postgres:secretpw@test_db:5432/marketplace_checkout_test"
    with pytest.raises(RuntimeError, match="endpoint"):
        validate_checkout_test_database_url(ci_url, ci=False)
    assert validate_checkout_test_database_url(ci_url, ci=True) == ci_url
    with pytest.raises(RuntimeError, match="endpoint"):
        validate_checkout_test_database_url(
            "postgresql+psycopg2://postgres:secretpw@test_db:5433/marketplace_checkout_test",
            ci=True,
        )

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        validate_checkout_test_database_url(good, app_database_url=good)
    assert validate_checkout_test_database_url(good, app_database_url="") == good
    for host in ("localhost", "127.0.0.1"):
        url = good.replace("127.0.0.1", host)
        assert validate_checkout_test_database_url(url, app_database_url="") == url


@pytest.mark.parametrize(
    "suffix",
    [
        "marketplace_checkout_test?host=prod.example.internal",
        "marketplace_checkout_test?dbname=marketplace",
        "marketplace_checkout_test_extra",
        "contains_test_word",
        "marketplace_checkout_test?",
    ],
)
def test_postgres_test_url_guard_rejects_independent_review_bypasses(suffix):
    """H1 regression: libpq query overrides and loose 'test' substring names are rejected."""
    url = "postgresql+psycopg2://postgres:secretpw@127.0.0.1:5433/" + suffix
    with pytest.raises(RuntimeError) as excinfo:
        validate_checkout_test_database_url(url, app_database_url="")
    message = str(excinfo.value)
    assert "secretpw" not in message
    assert url not in message


def test_postgres_test_url_guard_errors_never_leak_password():
    for bad in (
        "postgresql+psycopg2://postgres:secretpw@prod.internal:5432/marketplace",
        "postgresql+psycopg2://postgres:secretpw@127.0.0.1:5433/marketplace_checkout_test?x=1",
        "postgresql+psycopg2://postgres:secretpw@[bad/marketplace_checkout_test",
    ):
        with pytest.raises(RuntimeError) as excinfo:
            validate_checkout_test_database_url(bad, app_database_url="")
        assert "secretpw" not in str(excinfo.value)
        assert excinfo.value.__cause__ is None

# ----------------------------------------- PostgreSQL integration & TC-INV-01 suite


class _PgFixtureDataTracker:
    """Creates isolated rows in PostgreSQL and deletes ONLY those rows during teardown."""

    def __init__(self, pg_app, admin_engine):
        self.app = pg_app
        self.engine = admin_engine
        self.user_ids = set()
        self.artisan_ids = set()
        self.category_ids = set()
        self.product_ids = set()

    def create_buyer(self):
        tag = uuid.uuid4().hex[:10]
        with Session(self.engine) as sess, sess.begin():
            user = User(
                email=f"pg_buyer_{tag}@pes.edu",
                password_hash="pg-test-hash",
                full_name=f"PG Buyer {tag}",
                role="buyer",
            )
            sess.add(user)
            sess.flush()
            user_id = user.user_id
        self.user_ids.add(user_id)
        with self.app.app_context():
            token = create_access_token(
                identity=str(user_id), additional_claims={"role": "buyer"}
            )
        return user_id, {"Authorization": f"Bearer {token}"}

    def create_product(self, title, price, stock):
        tag = uuid.uuid4().hex[:10]
        with Session(self.engine) as sess, sess.begin():
            seller = User(
                email=f"pg_seller_{tag}@pes.edu",
                password_hash="pg-test-hash",
                full_name=f"PG Seller {tag}",
                role="artisan",
            )
            sess.add(seller)
            sess.flush()
            artisan = Artisan(user_id=seller.user_id, shop_name=f"PG Shop {tag}")
            category = Category(name=f"PG Cat {tag}", slug=f"pg-cat-{tag}")
            sess.add_all([artisan, category])
            sess.flush()
            product = Product(
                artisan_id=artisan.artisan_id,
                category_id=category.category_id,
                title=title,
                description=f"Handmade {title.lower()}",
                price=price,
                is_active=True,
            )
            sess.add(product)
            sess.flush()
            sess.add(
                Inventory(
                    product_id=product.product_id,
                    stock_quantity=stock,
                    low_stock_threshold=5,
                )
            )
            self.user_ids.add(seller.user_id)
            self.artisan_ids.add(artisan.artisan_id)
            self.category_ids.add(category.category_id)
            self.product_ids.add(product.product_id)
            return product.product_id

    def seed_cart_item(self, buyer_id, product_id, quantity, unit_price):
        with Session(self.engine) as sess, sess.begin():
            cart = sess.scalar(select(Cart).where(Cart.buyer_id == buyer_id))
            if cart is None:
                cart = Cart(buyer_id=buyer_id)
                sess.add(cart)
                sess.flush()
            sess.add(
                CartItem(
                    cart_id=cart.cart_id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                )
            )

    def cleanup(self):
        with Session(self.engine) as sess, sess.begin():
            order_ids = set()
            if self.user_ids:
                order_ids.update(
                    sess.scalars(
                        select(Order.order_id).where(Order.buyer_id.in_(self.user_ids))
                    ).all()
                )
            if self.product_ids:
                order_ids.update(
                    sess.scalars(
                        select(OrderItem.order_id).where(
                            OrderItem.product_id.in_(self.product_ids)
                        )
                    ).all()
                )
            if order_ids:
                sess.execute(delete(Invoice).where(Invoice.order_id.in_(order_ids)))
                sess.execute(delete(Payment).where(Payment.order_id.in_(order_ids)))
                sess.execute(delete(OrderItem).where(OrderItem.order_id.in_(order_ids)))
                sess.execute(delete(Order).where(Order.order_id.in_(order_ids)))
            if self.product_ids:
                sess.execute(
                    delete(OrderItem).where(OrderItem.product_id.in_(self.product_ids))
                )
                sess.execute(
                    delete(CartItem).where(CartItem.product_id.in_(self.product_ids))
                )
            if self.user_ids:
                cart_ids = sess.scalars(
                    select(Cart.cart_id).where(Cart.buyer_id.in_(self.user_ids))
                ).all()
                if cart_ids:
                    sess.execute(delete(CartItem).where(CartItem.cart_id.in_(cart_ids)))
                sess.execute(delete(Cart).where(Cart.buyer_id.in_(self.user_ids)))
            if self.product_ids:
                sess.execute(
                    delete(ProductImage).where(ProductImage.product_id.in_(self.product_ids))
                )
                sess.execute(
                    delete(Inventory).where(Inventory.product_id.in_(self.product_ids))
                )
                sess.execute(delete(Product).where(Product.product_id.in_(self.product_ids)))
            if self.artisan_ids:
                sess.execute(delete(Artisan).where(Artisan.artisan_id.in_(self.artisan_ids)))
            if self.category_ids:
                sess.execute(
                    delete(Category).where(Category.category_id.in_(self.category_ids))
                )
            if self.user_ids:
                sess.execute(delete(User).where(User.user_id.in_(self.user_ids)))


@pytest.fixture
def pg_checkout_env(deterministic_gateway):
    raw_url = os.getenv("CHECKOUT_TEST_DATABASE_URL")
    in_ci = _is_ci_environment()
    try:
        validated_url = validate_checkout_test_database_url(raw_url, ci=in_ci)
    except RuntimeError as exc:
        pytest.fail(str(exc))

    if validated_url is None:
        if in_ci:
            pytest.fail(
                "CHECKOUT_TEST_DATABASE_URL is required when CI=true; PostgreSQL "
                "integration tests must not be skipped in CI."
            )
        pytest.skip(
            "CHECKOUT_TEST_DATABASE_URL is not set; skipping PostgreSQL checkout "
            "integration tests (set it to the dedicated test database, see docker-compose "
            "'test' profile)."
        )

    # The exact validated URL is used for both engines; timeouts are passed as connection
    # options (not URL query parameters) so every PostgreSQL connection receives them.
    admin_engine = create_engine(
        validated_url, pool_pre_ping=True, connect_args=dict(PG_CONNECT_ARGS)
    )
    tracker = None
    pg_app = None
    try:
        # Create missing schema tables idempotently; never drop or truncate existing tables.
        db.metadata.create_all(bind=admin_engine, checkfirst=True)

        pg_app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": validated_url,
                "SQLALCHEMY_ENGINE_OPTIONS": {
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_pre_ping": True,
                    "connect_args": dict(PG_CONNECT_ARGS),
                },
                "JWT_SECRET_KEY": "test-secret-key-for-postgres-checkout-integration",
            }
        )
        tracker = _PgFixtureDataTracker(pg_app, admin_engine)
        yield pg_app, admin_engine, tracker, deterministic_gateway
    finally:
        # Each step is isolated so a failure in one never skips the later ones.
        try:
            if pg_app is not None:
                with pg_app.app_context():
                    try:
                        db.session.remove()
                    finally:
                        db.engine.dispose()
        finally:
            try:
                if tracker is not None:
                    tracker.cleanup()
            finally:
                admin_engine.dispose()


def _run_two_concurrent(fn_a, fn_b):
    """Run two callables concurrently; never block on shutdown of stuck worker threads."""
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        fut_a = pool.submit(fn_a)
        fut_b = pool.submit(fn_b)
        return fut_a.result(timeout=FUTURE_TIMEOUT), fut_b.result(timeout=FUTURE_TIMEOUT)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


@pytest.mark.postgres_integration
def test_tc_inv_01_concurrent_checkout_last_unit_postgres(pg_checkout_env):
    """TC-INV-01 (High) - OMH-F-015: Concurrent checkouts for stock=1 in PostgreSQL.

    Two buyers with independent Flask test clients and distinct PostgreSQL connections
    submit POST /api/checkout concurrently for the last remaining unit.
    """
    pg_app, admin_engine, tracker, gateway = pg_checkout_env

    product_id = tracker.create_product("Kashmiri Walnut Box", price=1200.00, stock=1)
    buyer_a_id, headers_a = tracker.create_buyer()
    buyer_b_id, headers_b = tracker.create_buyer()
    tracker.seed_cart_item(buyer_a_id, product_id, quantity=1, unit_price=1200.00)
    tracker.seed_cart_item(buyer_b_id, product_id, quantity=1, unit_price=1200.00)

    client_a = pg_app.test_client()
    client_b = pg_app.test_client()

    start_barrier = threading.Barrier(2, timeout=BARRIER_TIMEOUT)
    for_update_barrier = threading.Barrier(2, timeout=BARRIER_TIMEOUT)
    pid_lock = threading.Lock()
    observed_backend_pids = set()

    with pg_app.app_context():
        app_engine = db.engine

    def _sync_before_for_update(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement and "inventory" in statement.lower():
            raw_conn = getattr(conn.connection, "dbapi_connection", conn.connection)
            with pid_lock:
                observed_backend_pids.add(raw_conn.info.backend_pid)
            for_update_barrier.wait(timeout=BARRIER_TIMEOUT)

    def _submit_checkout(test_client, auth_headers, buyer_label):
        start_barrier.wait(timeout=BARRIER_TIMEOUT)
        response = test_client.post(
            CHECKOUT_URL,
            json={
                "shipping_address": f"Buyer {buyer_label}, 14 Residency Rd, Bengaluru",
                "payment_token": "tok_visa_success",
            },
            headers=auth_headers,
        )
        return response.status_code, response.get_json()

    event.listen(app_engine, "before_cursor_execute", _sync_before_for_update)
    try:
        (status_a, body_a), (status_b, body_b) = _run_two_concurrent(
            lambda: _submit_checkout(client_a, headers_a, "A"),
            lambda: _submit_checkout(client_b, headers_b, "B"),
        )
    finally:
        event.remove(app_engine, "before_cursor_execute", _sync_before_for_update)

    # Confirm two separate PostgreSQL backend connections executed SELECT ... FOR UPDATE.
    assert len(observed_backend_pids) == 2

    outcomes = [(buyer_a_id, status_a, body_a), (buyer_b_id, status_b, body_b)]
    assert sorted([status_a, status_b]) == [201, 400]

    winner_id, _, winner_body = next(item for item in outcomes if item[1] == 201)
    loser_id, _, loser_body = next(item for item in outcomes if item[1] == 400)

    assert winner_body["status"] == "Processing"
    assert winner_body["payment_status"] == "captured"
    assert winner_body["total"] == 1200.0
    assert winner_body["transaction_ref"] == "TXN-MOCK-000001"

    assert loser_body["error"] == "INSUFFICIENT_STOCK"
    assert "Kashmiri Walnut Box" in loser_body["message"]
    assert "0 unit(s) available" in loser_body["message"]

    # Verify final database state directly in PostgreSQL via an independent session.
    with Session(admin_engine) as verify_sess:
        inv = verify_sess.scalar(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        assert inv is not None
        assert inv.stock_quantity == 0
        assert inv.stock_quantity >= 0

        product_order_items = verify_sess.scalars(
            select(OrderItem).where(OrderItem.product_id == product_id)
        ).all()
        assert len(product_order_items) == 1
        assert product_order_items[0].quantity == 1
        assert product_order_items[0].unit_price == Decimal("1200.00")

        buyer_orders = verify_sess.scalars(
            select(Order).where(Order.buyer_id.in_([buyer_a_id, buyer_b_id]))
        ).all()
        assert len(buyer_orders) == 1
        assert buyer_orders[0].order_id == winner_body["order_id"]
        assert buyer_orders[0].buyer_id == winner_id
        assert buyer_orders[0].status == "Processing"

        payments = verify_sess.scalars(
            select(Payment).where(Payment.order_id == buyer_orders[0].order_id)
        ).all()
        assert len(payments) == 1
        assert payments[0].payment_status == "captured"
        assert payments[0].transaction_ref == "TXN-MOCK-000001"

        winner_cart_items = verify_sess.scalars(
            select(CartItem).join(Cart).where(Cart.buyer_id == winner_id)
        ).all()
        loser_cart_items = verify_sess.scalars(
            select(CartItem).join(Cart).where(Cart.buyer_id == loser_id)
        ).all()
        assert winner_cart_items == []
        assert len(loser_cart_items) == 1
        assert loser_cart_items[0].quantity == 1

    assert len(gateway.captures) == 1
    assert gateway.refunds == []


@pytest.mark.postgres_integration
def test_postgres_concurrent_reverse_order_multi_item_carts_avoid_deadlock(pg_checkout_env):
    """Verify sorted product ID locking prevents PostgreSQL deadlocks on multi-item carts."""
    pg_app, admin_engine, tracker, gateway = pg_checkout_env

    prod_1 = tracker.create_product("Brass Diya", price=400.00, stock=1)
    prod_2 = tracker.create_product("Copper Kalash", price=600.00, stock=1)
    buyer_a_id, headers_a = tracker.create_buyer()
    buyer_b_id, headers_b = tracker.create_buyer()

    # Insert cart items in opposite order so unsorted locking would risk AB/BA deadlock.
    tracker.seed_cart_item(buyer_a_id, prod_1, quantity=1, unit_price=400.00)
    tracker.seed_cart_item(buyer_a_id, prod_2, quantity=1, unit_price=600.00)
    tracker.seed_cart_item(buyer_b_id, prod_2, quantity=1, unit_price=600.00)
    tracker.seed_cart_item(buyer_b_id, prod_1, quantity=1, unit_price=400.00)

    client_a = pg_app.test_client()
    client_b = pg_app.test_client()
    start_barrier = threading.Barrier(2, timeout=BARRIER_TIMEOUT)

    def _run(test_client, auth_headers):
        start_barrier.wait(timeout=BARRIER_TIMEOUT)
        resp = test_client.post(
            CHECKOUT_URL,
            json={
                "shipping_address": "99 Commercial Street, Bengaluru",
                "payment_token": "tok_visa_success",
            },
            headers=auth_headers,
        )
        return resp.status_code, resp.get_json()

    (status_a, _), (status_b, _) = _run_two_concurrent(
        lambda: _run(client_a, headers_a),
        lambda: _run(client_b, headers_b),
    )

    assert sorted([status_a, status_b]) == [201, 400]

    with Session(admin_engine) as verify_sess:
        stocks = {
            row.product_id: row.stock_quantity
            for row in verify_sess.scalars(
                select(Inventory).where(Inventory.product_id.in_([prod_1, prod_2]))
            ).all()
        }
        assert stocks == {prod_1: 0, prod_2: 0}
        orders = verify_sess.scalars(
            select(Order).where(Order.buyer_id.in_([buyer_a_id, buyer_b_id]))
        ).all()
        assert len(orders) == 1
    assert len(gateway.captures) == 1
    assert gateway.refunds == []


@pytest.mark.postgres_integration
def test_postgres_decline_and_commit_failure_release_locks_and_preserve_consistency(
    pg_checkout_env, monkeypatch
):
    """Verify PostgreSQL row-lock release on 402 decline and rollback+refund on commit error."""
    pg_app, admin_engine, tracker, gateway = pg_checkout_env

    # Sentinel unrelated user/product to prove teardown only removes tracked fixture data.
    sentinel_tag = uuid.uuid4().hex[:10]
    with Session(admin_engine) as sess, sess.begin():
        sentinel_user = User(
            email=f"sentinel_{sentinel_tag}@pes.edu",
            password_hash="sentinel-hash",
            full_name="Preexisting User",
            role="buyer",
        )
        sess.add(sentinel_user)
        sess.flush()
        sentinel_user_id = sentinel_user.user_id

    try:
        product_id = tracker.create_product("Bidriware Coaster", price=900.00, stock=1)
        buyer_a_id, headers_a = tracker.create_buyer()
        buyer_b_id, headers_b = tracker.create_buyer()
        tracker.seed_cart_item(buyer_a_id, product_id, quantity=1, unit_price=900.00)
        tracker.seed_cart_item(buyer_b_id, product_id, quantity=1, unit_price=900.00)

        client_a = pg_app.test_client()
        client_b = pg_app.test_client()

        # 1. Buyer A declines -> HTTP 402; PostgreSQL row lock released and stock remains 1.
        declined = client_a.post(
            CHECKOUT_URL,
            json={
                "shipping_address": "1 MG Road, Bengaluru",
                "payment_token": "tok_charge_declined",
            },
            headers=headers_a,
        )
        assert declined.status_code == 402

        # 2. Buyer B simulates DB commit failure after payment capture -> HTTP 500 + refund.
        with pg_app.app_context():
            real_commit = db.session.commit

        def _fail_once():
            raise OperationalError("COMMIT", {}, Exception("simulated pg commit error"))

        monkeypatch.setattr(db.session, "commit", _fail_once)
        failed = client_b.post(
            CHECKOUT_URL,
            json={
                "shipping_address": "2 MG Road, Bengaluru",
                "payment_token": "tok_visa_success",
            },
            headers=headers_b,
        )
        assert failed.status_code == 500
        assert len(gateway.captures) == 1
        assert len(gateway.refunds) == 1
        assert gateway.refunds[0]["transaction_ref"] == gateway.captures[0]["transaction_ref"]

        # 3. Restore commit; Buyer B retries and succeeds because previous tx rolled back!
        monkeypatch.setattr(db.session, "commit", real_commit)
        succeeded = client_b.post(
            CHECKOUT_URL,
            json={
                "shipping_address": "2 MG Road, Bengaluru",
                "payment_token": "tok_visa_success",
            },
            headers=headers_b,
        )
        assert succeeded.status_code == 201, succeeded.get_json()

        with Session(admin_engine) as verify_sess:
            inv = verify_sess.scalar(
                select(Inventory).where(Inventory.product_id == product_id)
            )
            assert inv.stock_quantity == 0
            orders = verify_sess.scalars(
                select(Order).where(Order.buyer_id.in_([buyer_a_id, buyer_b_id]))
            ).all()
            assert len(orders) == 1
            assert orders[0].buyer_id == buyer_b_id

        # Verify tracker.cleanup() removes tracked rows without touching sentinel_user.
        tracker.cleanup()
        with Session(admin_engine) as verify_sess:
            assert verify_sess.get(User, sentinel_user_id) is not None
            assert verify_sess.get(Product, product_id) is None
    finally:
        with Session(admin_engine) as sess, sess.begin():
            sess.execute(delete(User).where(User.user_id == sentinel_user_id))
