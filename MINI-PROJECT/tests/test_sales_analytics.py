"""Test suite for Jira SE8-36: Artisan Sales Analytics.

Requirement mapping: OMH-F-019 / TC-RPT-01.
"""
from datetime import datetime, timedelta, timezone
import uuid

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import (
    Artisan,
    Category,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Product,
    User,
)

PASSWORD = "StrongP@ss123"
ADDRESS = "100 MG Road, Bengaluru 560001"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------
def _create_artisan(shop_name="Studio"):
    """Create an artisan user and profile, returning (user, artisan)."""
    tag = uuid.uuid4().hex[:8]
    user = User(
        email=f"artisan_{tag}@pes.edu",
        password_hash="fake-hash",
        full_name=f"Artisan {tag}",
        role="artisan",
    )
    db.session.add(user)
    db.session.flush()

    artisan = Artisan(
        user_id=user.user_id,
        shop_name=f"{shop_name} {tag}",
        bio="Handcrafted items with love",
    )
    db.session.add(artisan)
    db.session.flush()
    return user, artisan


def _artisan_token(user_id):
    token = create_access_token(
        identity=str(user_id), additional_claims={"role": "artisan"}
    )
    return {"Authorization": f"Bearer {token}"}


def _buyer_token(user_id=None):
    if user_id is None:
        tag = uuid.uuid4().hex[:8]
        user = User(
            email=f"buyer_{tag}@pes.edu",
            password_hash="fake-hash",
            full_name="Buyer User",
            role="buyer",
        )
        db.session.add(user)
        db.session.flush()
        user_id = user.user_id
    token = create_access_token(
        identity=str(user_id), additional_claims={"role": "buyer"}
    )
    return {"Authorization": f"Bearer {token}"}


def _create_product(artisan_id, title, price, stock=20):
    tag = uuid.uuid4().hex[:8]
    cat = Category(name=f"Cat {tag}", slug=f"cat-{tag}")
    db.session.add(cat)
    db.session.flush()

    prod = Product(
        artisan_id=artisan_id,
        category_id=cat.category_id,
        title=title,
        description=f"Authentic {title}",
        price=price,
        is_active=True,
    )
    db.session.add(prod)
    db.session.flush()
    db.session.add(
        Inventory(
            product_id=prod.product_id,
            stock_quantity=stock,
            low_stock_threshold=5,
        )
    )
    db.session.flush()
    return prod


def _create_order(
    buyer_id,
    lines,
    status="Processing",
    payment_status="captured",
    created_at=None,
):
    """Create an order with given line items [(product, qty, price), ...]."""
    total = sum(q * p for _, q, p in lines)
    order = Order(
        buyer_id=buyer_id,
        total_amount=total,
        status=status,
        shipping_address=ADDRESS,
    )
    if created_at is not None:
        order.created_at = created_at
    db.session.add(order)
    db.session.flush()

    for prod, qty, price in lines:
        db.session.add(
            OrderItem(
                order_id=order.order_id,
                product_id=prod.product_id,
                quantity=qty,
                unit_price=price,
            )
        )

    if payment_status is not None:
        ref = f"TXN-{uuid.uuid4().hex[:10]}"
        db.session.add(
            Payment(
                order_id=order.order_id,
                transaction_ref=ref,
                amount=total,
                payment_status=payment_status,
                paid_at=created_at or datetime.now(timezone.utc),
            )
        )
    db.session.commit()
    return order


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
def test_tc_rpt_01_three_completed_orders_stp_scenario(client):
    """TC-RPT-01 from STP:

    3 completed orders for Artisan totaling 1200.00.
    GET /api/reports/sales?period=monthly returns revenue=1200.0,
    order_count=3, and correct craft breakdown.
    """
    user, artisan = _create_artisan("Pottery Barn")
    p1 = _create_product(artisan.artisan_id, "Ceramic Mug", 300.0)
    p2 = _create_product(artisan.artisan_id, "Clay Pot", 600.0)

    # Order 1: 1 mug @ 300 = 300
    # Order 2: 1 mug @ 300 = 300
    # Order 3: 1 pot @ 600 = 600
    # Total = 1200
    _create_order(
        999, [(p1, 1, 300.0)], status="Processing", payment_status="captured"
    )
    _create_order(
        999, [(p1, 1, 300.0)], status="Shipped", payment_status="captured"
    )
    _create_order(
        999, [(p2, 1, 600.0)], status="Delivered", payment_status="captured"
    )

    headers = _artisan_token(user.user_id)
    resp = client.get("/api/reports/sales?period=monthly", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["revenue"] == 1200.0
    assert data["gross_revenue"] == 1200.0
    assert data["order_count"] == 3
    assert data["units_sold"] == 3
    assert data["units"] == 3

    assert len(data["top_items"]) == 2
    # p1 sold 2 units, p2 sold 1 unit -> p1 is top item by units sold
    assert data["top_items"][0]["title"] == "Ceramic Mug"
    assert data["top_items"][0]["units_sold"] == 2
    assert data["top_items"][0]["revenue"] == 600.0

    assert data["top_items"][1]["title"] == "Clay Pot"
    assert data["top_items"][1]["units_sold"] == 1
    assert data["top_items"][1]["revenue"] == 600.0


def test_artisan_data_isolation(client):
    """Verify strict multi-vendor artisan isolation:

    Artisan A only sees sales and analytics for their own products.
    Artisan B only sees sales and analytics for their own products.
    Mixed orders partition revenue and units correctly.
    """
    user_a, artisan_a = _create_artisan("Artisan A Studio")
    user_b, artisan_b = _create_artisan("Artisan B Workshop")

    p_a1 = _create_product(artisan_a.artisan_id, "Handmade Scarf", 500.0)
    p_a2 = _create_product(artisan_a.artisan_id, "Silk Tie", 250.0)
    p_b1 = _create_product(artisan_b.artisan_id, "Wooden Bowl", 800.0)

    # Order 1 (mixed): 2 scarves from A (1000) + 1 bowl from B (800)
    _create_order(
        1001,
        [(p_a1, 2, 500.0), (p_b1, 1, 800.0)],
        status="Processing",
        payment_status="captured",
    )

    # Order 2 (A only): 1 tie from A (250)
    _create_order(
        1002,
        [(p_a2, 1, 250.0)],
        status="Shipped",
        payment_status="captured",
    )

    # Order 3 (B only): 2 bowls from B (1600)
    _create_order(
        1003,
        [(p_b1, 2, 800.0)],
        status="Delivered",
        payment_status="captured",
    )

    # Check Artisan A analytics
    tok_a = _artisan_token(user_a.user_id)
    resp_a = client.get("/api/reports/sales?period=monthly", headers=tok_a)
    assert resp_a.status_code == 200
    data_a = resp_a.get_json()
    assert data_a["revenue"] == 1250.0  # 1000 + 250
    assert data_a["units_sold"] == 3    # 2 scarves + 1 tie
    assert data_a["order_count"] == 2   # Order 1 and Order 2
    assert len(data_a["top_items"]) == 2
    expected_ids = (p_a1.product_id, p_a2.product_id)
    assert all(i["product_id"] in expected_ids for i in data_a["top_items"])

    # Check Artisan B analytics
    tok_b = _artisan_token(user_b.user_id)
    resp_b = client.get("/api/reports/sales?period=monthly", headers=tok_b)
    assert resp_b.status_code == 200
    data_b = resp_b.get_json()
    assert data_b["revenue"] == 2400.0  # 800 + 1600
    assert data_b["units_sold"] == 3    # 1 bowl + 2 bowls
    assert data_b["order_count"] == 2   # Order 1 and Order 3
    assert len(data_b["top_items"]) == 1
    assert data_b["top_items"][0]["product_id"] == p_b1.product_id


def test_auth_and_rbac_enforcement(client):
    """Test authentication and role authorization:

    - No auth header -> 401
    - Buyer role -> 403
    - Artisan role without Artisan profile in DB -> 403
    """
    # 1. Unauthenticated
    assert client.get("/api/reports/sales").status_code == 401

    # 2. Buyer role
    resp = client.get("/api/reports/sales", headers=_buyer_token())
    assert resp.status_code == 403
    assert "Artisan privilege required" in resp.get_json()["message"]

    # 3. User with artisan role but no Artisan profile table row
    user_orphan = User(
        email=f"orphan_{uuid.uuid4().hex[:6]}@pes.edu",
        password_hash="fake-hash",
        full_name="Orphan Artisan",
        role="artisan",
    )
    db.session.add(user_orphan)
    db.session.commit()

    resp_orphan = client.get(
        "/api/reports/sales", headers=_artisan_token(user_orphan.user_id)
    )
    assert resp_orphan.status_code == 403
    assert "Artisan profile required" in resp_orphan.get_json()["message"]


def test_empty_datasets(client):
    """Test artisan with no sales or products returns 200 with zero metrics."""
    user, artisan = _create_artisan("Empty Shop")
    # Artisan has no products and no orders
    tok = _artisan_token(user.user_id)
    resp = client.get("/api/reports/sales", headers=tok)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["revenue"] == 0.0
    assert data["gross_revenue"] == 0.0
    assert data["order_count"] == 0
    assert data["units_sold"] == 0
    assert data["units"] == 0
    assert data["top_items"] == []

    # Artisan creates a product but no orders exist yet
    _create_product(artisan.artisan_id, "Unsold Craft", 150.0)
    resp2 = client.get(
        "/api/reports/sales", headers=_artisan_token(user.user_id)
    )
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["revenue"] == 0.0
    assert data2["order_count"] == 0
    assert data2["top_items"] == []


def test_order_status_and_payment_filtering(client):
    """Test that only valid completed orders with captured payment are counted.

    - Pending order (unpaid/incomplete checkout) -> excluded
    - Cancelled order -> excluded
    - Refunded payment -> excluded
    - Failed payment -> excluded
    - Processing / Shipped / Delivered with captured payment -> included
    """
    user, artisan = _create_artisan("Status Shop")
    prod = _create_product(artisan.artisan_id, "Status Vase", 100.0)

    # Valid Processing
    _create_order(
        2001, [(prod, 1, 100.0)],
        status="Processing", payment_status="captured",
    )
    # Valid Shipped
    _create_order(
        2002, [(prod, 1, 100.0)], status="Shipped", payment_status="captured"
    )
    # Valid Delivered
    _create_order(
        2003, [(prod, 1, 100.0)],
        status="Delivered", payment_status="captured",
    )

    # Pending order (unpaid / abandoned)
    _create_order(
        2004, [(prod, 2, 100.0)], status="Pending", payment_status="pending"
    )

    # Refunded order
    _create_order(
        2005, [(prod, 3, 100.0)],
        status="Processing", payment_status="refunded",
    )

    # Failed payment
    _create_order(
        2006, [(prod, 4, 100.0)], status="Processing", payment_status="failed"
    )

    # Order without any payment record (unpaid / corrupt)
    _create_order(
        2007, [(prod, 5, 100.0)],
        status="Processing", payment_status=None,
    )

    headers = _artisan_token(user.user_id)
    resp = client.get("/api/reports/sales?period=monthly", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()

    # Only the 3 valid orders should be counted
    assert data["revenue"] == 300.0
    assert data["units_sold"] == 3
    assert data["order_count"] == 3


def test_date_range_and_period_filtering(client):
    """Test various period keywords and custom date filtering."""
    user, artisan = _create_artisan("Date Filter Shop")
    prod = _create_product(artisan.artisan_id, "Calendar Craft", 200.0)

    now = datetime.now(timezone.utc)
    # Order this month
    _create_order(
        3001, [(prod, 1, 200.0)], status="Processing", created_at=now
    )

    # Order 60 days ago
    past_order_time = now - timedelta(days=60)
    _create_order(
        3002,
        [(prod, 2, 200.0)],
        status="Delivered",
        created_at=past_order_time,
    )

    headers = _artisan_token(user.user_id)

    # 1. period=monthly includes only current month's order
    resp_month = client.get(
        "/api/reports/sales?period=monthly", headers=headers
    )
    assert resp_month.status_code == 200
    data_month = resp_month.get_json()
    assert data_month["revenue"] == 200.0
    assert data_month["units_sold"] == 1
    assert data_month["order_count"] == 1

    # 2. period=all includes both orders
    resp_all = client.get("/api/reports/sales?period=all", headers=headers)
    assert resp_all.status_code == 200
    data_all = resp_all.get_json()
    assert data_all["revenue"] == 600.0
    assert data_all["units_sold"] == 3
    assert data_all["order_count"] == 2

    # 3. Custom start_date and end_date targeting the past order
    start_str = (past_order_time - timedelta(days=1)).strftime("%Y-%m-%d")
    end_str = (past_order_time + timedelta(days=1)).strftime("%Y-%m-%d")
    resp_custom = client.get(
        f"/api/reports/sales?start_date={start_str}&end_date={end_str}",
        headers=headers,
    )
    assert resp_custom.status_code == 200
    data_custom = resp_custom.get_json()
    assert data_custom["revenue"] == 400.0
    assert data_custom["units_sold"] == 2
    assert data_custom["order_count"] == 1


def test_historical_unit_prices_respected(client):
    """Analytics must use historical unit price from OrderItem."""
    user, artisan = _create_artisan("Price History Shop")
    prod = _create_product(artisan.artisan_id, "Vintage Table", 100.0)

    # Order 1 was placed when price was 100
    _create_order(4001, [(prod, 2, 100.0)], status="Processing")

    # Artisan subsequently raises product catalog price to 300
    prod.price = 300.0
    db.session.commit()

    # Order 2 was placed at the new price 300
    _create_order(4002, [(prod, 1, 300.0)], status="Processing")

    headers = _artisan_token(user.user_id)
    resp = client.get("/api/reports/sales?period=monthly", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()

    # Total revenue must be (2 * 100) + (1 * 300) = 500.0
    assert data["revenue"] == 500.0
    assert data["units_sold"] == 3
    assert data["order_count"] == 2
    assert data["top_items"][0]["revenue"] == 500.0


def test_invalid_requests_and_validation_errors(client):
    """Test validation errors for invalid period and dates."""
    user, artisan = _create_artisan("Validation Shop")
    headers = _artisan_token(user.user_id)

    # 1. Invalid period
    resp1 = client.get(
        "/api/reports/sales?period=nonexistent", headers=headers
    )
    assert resp1.status_code == 400
    assert resp1.get_json()["error"] == "INVALID_PERIOD"

    # 2. Malformed start_date
    resp2 = client.get(
        "/api/reports/sales?start_date=2026-13-45", headers=headers
    )
    assert resp2.status_code == 400
    assert resp2.get_json()["error"] == "INVALID_DATE_FORMAT"

    # 3. Inverted range (start_date > end_date)
    resp3 = client.get(
        "/api/reports/sales?start_date=2026-11-10&end_date=2026-11-01",
        headers=headers,
    )
    assert resp3.status_code == 400
    assert resp3.get_json()["error"] == "INVALID_DATE_RANGE"

    # 4. Invalid limit
    resp4 = client.get("/api/reports/sales?limit=-5", headers=headers)
    assert resp4.status_code == 400
    assert resp4.get_json()["error"] == "INVALID_INPUT"
