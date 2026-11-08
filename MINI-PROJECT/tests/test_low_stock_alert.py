"""Tests for SE8-33 / OMH-F-016: Low-Stock Dashboard Alerts & Threshold Configuration."""
from decimal import Decimal
import uuid

from flask_jwt_extended import create_access_token

from app.checkout.stock import check_low_stock, decrement_stock, lock_and_validate_stock
from app.models import Artisan, Category, Inventory, Product, User


# ---------------------------------------------------------------- helpers
def _create_artisan(db, email=None, shop_name="Handcraft Studio"):
    tag = uuid.uuid4().hex[:8]
    user = User(
        email=email or f"artisan_{tag}@pes.edu",
        password_hash="hashed_pw_dummy",
        full_name="Artisan Tester",
        role="artisan",
    )
    db.session.add(user)
    db.session.flush()

    artisan = Artisan(
        user_id=user.user_id,
        shop_name=shop_name,
        bio="Test artisan bio",
    )
    db.session.add(artisan)
    db.session.commit()
    return user, artisan


def _create_buyer(db, email=None):
    tag = uuid.uuid4().hex[:8]
    user = User(
        email=email or f"buyer_{tag}@pes.edu",
        password_hash="hashed_pw_dummy",
        full_name="Buyer Tester",
        role="buyer",
    )
    db.session.add(user)
    db.session.commit()
    return user


def _auth_headers(user):
    token = create_access_token(
        identity=str(user.user_id),
        additional_claims={"role": user.role},
    )
    return {"Authorization": f"Bearer {token}"}


def _create_product(db, artisan, title="Clay Mug", price=250.00, stock=10,
                    threshold=5, is_active=True):
    tag = uuid.uuid4().hex[:8]
    category = Category(name=f"Crafts {tag}", slug=f"crafts-{tag}")
    db.session.add(category)
    db.session.flush()

    product = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description=f"Authentic {title.lower()}",
        price=Decimal(str(price)),
        is_active=is_active,
    )
    db.session.add(product)
    db.session.flush()

    inv = Inventory(
        product_id=product.product_id,
        stock_quantity=stock,
        low_stock_threshold=threshold,
    )
    db.session.add(inv)
    db.session.commit()
    return product, inv


# =========================================================================
# 1. Dashboard Alert Behaviour (OMH-F-016 / TC-INV-02)
# =========================================================================
def test_stock_above_threshold_excluded_from_alert(client, db):
    """Stock 6, threshold 5 -> excluded from low_stock."""
    user, artisan = _create_artisan(db)
    _create_product(db, artisan, title="Stock 6 Lamp", stock=6, threshold=5)

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 200
    data = res.get_json()
    assert "low_stock" in data
    assert data["low_stock"] == []


def test_stock_equal_threshold_included_in_alert(client, db):
    """Stock 5, threshold 5 -> included in low_stock (boundary condition)."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Stock 5 Lamp", stock=5, threshold=5)

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 200
    items = res.get_json()["low_stock"]
    assert len(items) == 1
    assert items[0]["product_id"] == prod.product_id
    assert items[0]["title"] == "Stock 5 Lamp"
    assert items[0]["stock_quantity"] == 5
    assert items[0]["threshold"] == 5


def test_stock_below_threshold_included_in_alert(client, db):
    """Stock 4, threshold 5 -> included in low_stock."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Stock 4 Lamp", stock=4, threshold=5)

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 200
    items = res.get_json()["low_stock"]
    assert len(items) == 1
    assert items[0]["product_id"] == prod.product_id
    assert items[0]["stock_quantity"] == 4


def test_stock_zero_included_in_alert(client, db):
    """Stock 0, threshold 5 -> included in low_stock."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Stock 0 Lamp", stock=0, threshold=5)

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 200
    items = res.get_json()["low_stock"]
    assert len(items) == 1
    assert items[0]["product_id"] == prod.product_id
    assert items[0]["stock_quantity"] == 0


def test_restock_removes_alert(client, db):
    """When stock is replenished above threshold, product is excluded from alerts."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Replenish Lamp", stock=4, threshold=5)

    # Initially low
    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert len(res.get_json()["low_stock"]) == 1

    # Replenish via product update API to stock 10
    update_res = client.put(
        f"/api/products/{prod.product_id}",
        json={"stock_qty": 10},
        headers=_auth_headers(user),
    )
    assert update_res.status_code == 200

    # Dashboard should now be empty
    res2 = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res2.status_code == 200
    assert res2.get_json()["low_stock"] == []


def test_multiple_qualifying_products_deduplicated_and_sorted(client, db):
    """Multiple qualifying products returned exactly once each, ordered lowest stock first."""
    user, artisan = _create_artisan(db)
    p1, _ = _create_product(db, artisan, title="Item A", stock=4, threshold=5)
    p2, _ = _create_product(db, artisan, title="Item B", stock=1, threshold=5)
    _create_product(db, artisan, title="Item C (Healthy)", stock=15, threshold=5)

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 200
    items = res.get_json()["low_stock"]
    assert len(items) == 2
    # Verify lowest stock (1) appears before (4)
    assert items[0]["product_id"] == p2.product_id
    assert items[0]["stock_quantity"] == 1
    assert items[1]["product_id"] == p1.product_id
    assert items[1]["stock_quantity"] == 4


def test_inactive_or_soft_deleted_product_excluded(client, db):
    """Inactive products (is_active=False) do not generate dashboard alerts."""
    user, artisan = _create_artisan(db)
    _create_product(db, artisan, title="Archived Lamp", stock=2, threshold=5, is_active=False)

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 200
    assert res.get_json()["low_stock"] == []


# =========================================================================
# 2. Ownership and Authorization
# =========================================================================
def test_artisan_sees_only_own_products(client, db):
    """Artisan A's low stock products are not visible to Artisan B."""
    artisan_a_user, artisan_a = _create_artisan(db, email="artisan_a@pes.edu", shop_name="Shop A")
    artisan_b_user, artisan_b = _create_artisan(db, email="artisan_b@pes.edu", shop_name="Shop B")

    prod_a, _ = _create_product(db, artisan_a, title="Artisan A Pot", stock=2, threshold=5)
    _create_product(db, artisan_b, title="Artisan B Pot", stock=20, threshold=5)

    # Artisan A sees prod_a
    res_a = client.get("/api/seller/dashboard", headers=_auth_headers(artisan_a_user))
    assert res_a.status_code == 200
    items_a = res_a.get_json()["low_stock"]
    assert len(items_a) == 1
    assert items_a[0]["product_id"] == prod_a.product_id

    # Artisan B sees empty low_stock
    res_b = client.get("/api/seller/dashboard", headers=_auth_headers(artisan_b_user))
    assert res_b.status_code == 200
    assert res_b.get_json()["low_stock"] == []


def test_buyer_cannot_access_seller_dashboard(client, db):
    """Buyer role receives HTTP 403 FORBIDDEN."""
    buyer = _create_buyer(db)
    res = client.get("/api/seller/dashboard", headers=_auth_headers(buyer))
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"


def test_unauthenticated_request_rejected(client):
    """Unauthenticated request receives HTTP 401 UNAUTHORIZED."""
    res = client.get("/api/seller/dashboard")
    assert res.status_code == 401
    assert res.get_json()["error"] == "UNAUTHORIZED"


def test_artisan_without_profile_returns_403(client, db):
    """User with artisan role claim but no Artisan row returns HTTP 403."""
    user = User(
        email="ghost_artisan@pes.edu",
        password_hash="pwd",
        full_name="Ghost Artisan",
        role="artisan",
    )
    db.session.add(user)
    db.session.commit()

    res = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"
    assert "Artisan profile required" in res.get_json()["message"]


# =========================================================================
# 3. Threshold Configuration & Validation
# =========================================================================
def test_create_product_default_threshold_is_five(client, app, db):
    """When low_stock_threshold is omitted, default threshold is 5."""
    user, artisan = _create_artisan(db)
    cat = Category(name="Cat Defaults", slug="cat-defaults")
    db.session.add(cat)
    db.session.commit()

    res = client.post(
        "/api/products",
        json={
            "title": "Default Threshold Bowl",
            "description": "Lovely handcrafted wooden bowl",
            "category_id": cat.category_id,
            "price": 120.00,
            "stock_qty": 15,
        },
        headers=_auth_headers(user),
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["low_stock_threshold"] == 5

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == body["product_id"])
        )
        assert inv.low_stock_threshold == 5


def test_create_product_with_custom_threshold(client, app, db):
    """Artisan can configure a custom low_stock_threshold upon creation."""
    user, artisan = _create_artisan(db)
    cat = Category(name="Cat Custom", slug="cat-custom")
    db.session.add(cat)
    db.session.commit()

    res = client.post(
        "/api/products",
        json={
            "title": "Custom Threshold Tapestry",
            "description": "Handmade wall hanging tapestry",
            "category_id": cat.category_id,
            "price": 850.00,
            "stock_qty": 15,
            "low_stock_threshold": 10,
        },
        headers=_auth_headers(user),
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["low_stock_threshold"] == 10

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == body["product_id"])
        )
        assert inv.low_stock_threshold == 10


def test_create_product_invalid_threshold_rejected(client, db):
    """Negative, boolean, float, and non-numeric thresholds return HTTP 422."""
    user, artisan = _create_artisan(db)
    cat = Category(name="Cat Bad Thresh", slug="cat-bad-thresh")
    db.session.add(cat)
    db.session.commit()

    base_payload = {
        "title": "Invalid Threshold Item",
        "description": "Nice handcrafted item with bad threshold",
        "category_id": cat.category_id,
        "price": 100.00,
        "stock_qty": 10,
    }

    for bad_val in [-1, True, False, 4.5, "not-a-number"]:
        payload = dict(base_payload, low_stock_threshold=bad_val)
        res = client.post(
            "/api/products",
            json=payload,
            headers=_auth_headers(user),
        )
        assert res.status_code == 422, f"Expected 422 for threshold={bad_val}"
        assert res.get_json()["error"] == "VALIDATION_ERROR"


def test_update_product_threshold(client, app, db):
    """Artisan can update their own product's low_stock_threshold via PUT."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Updatable Bowl", stock=7, threshold=5)

    # At stock 7, threshold 5 -> not low stock
    res1 = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    assert res1.get_json()["low_stock"] == []

    # Update threshold to 8
    put_res = client.put(
        f"/api/products/{prod.product_id}",
        json={"low_stock_threshold": 8},
        headers=_auth_headers(user),
    )
    assert put_res.status_code == 200
    assert put_res.get_json()["low_stock_threshold"] == 8

    # Now stock 7 <= threshold 8 -> alert appears!
    res2 = client.get("/api/seller/dashboard", headers=_auth_headers(user))
    items = res2.get_json()["low_stock"]
    assert len(items) == 1
    assert items[0]["product_id"] == prod.product_id
    assert items[0]["threshold"] == 8


def test_update_product_invalid_threshold_rejected(client, db):
    """Updating threshold with negative, boolean, float, or invalid string returns 422."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, stock=10, threshold=5)

    for bad_val in [-5, True, False, 2.5, "five", None]:
        res = client.put(
            f"/api/products/{prod.product_id}",
            json={"low_stock_threshold": bad_val},
            headers=_auth_headers(user),
        )
        assert res.status_code == 422, f"Expected 422 for threshold={bad_val}"
        assert res.get_json()["error"] == "VALIDATION_ERROR"


def test_non_owner_cannot_update_threshold(client, db):
    """Artisan B cannot update Artisan A's product threshold."""
    user_a, artisan_a = _create_artisan(db, email="owner_a@pes.edu")
    user_b, _ = _create_artisan(db, email="intruder_b@pes.edu")
    prod, _ = _create_product(db, artisan_a, stock=10, threshold=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"low_stock_threshold": 12},
        headers=_auth_headers(user_b),
    )
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"


def test_buyer_cannot_update_threshold(client, db):
    """Buyer receives HTTP 403 when trying to update product threshold."""
    user_a, artisan_a = _create_artisan(db)
    buyer = _create_buyer(db)
    prod, _ = _create_product(db, artisan_a, stock=10, threshold=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"low_stock_threshold": 12},
        headers=_auth_headers(buyer),
    )
    assert res.status_code == 403


# =========================================================================
# 4. Inventory Service Integration & Stock Locking
# =========================================================================
def test_check_low_stock_helper(db):
    """check_low_stock returns detailed dict and is_low_stock boolean without locks."""
    user, artisan = _create_artisan(db)
    p_low, _ = _create_product(db, artisan, title="Low Item", stock=3, threshold=5)
    p_high, _ = _create_product(db, artisan, title="High Item", stock=10, threshold=5)

    res_low = check_low_stock(p_low.product_id, db_sess=db.session)
    assert res_low is not None
    assert res_low["product_id"] == p_low.product_id
    assert res_low["stock_quantity"] == 3
    assert res_low["threshold"] == 5
    assert res_low["is_low_stock"] is True

    res_high = check_low_stock(p_high.product_id, db_sess=db.session)
    assert res_high is not None
    assert res_high["is_low_stock"] is False


def test_check_low_stock_nonexistent_product(db):
    """check_low_stock returns None when product inventory does not exist."""
    res = check_low_stock(999999, db_sess=db.session)
    assert res is None


def test_atomic_stock_locking_and_decrement_integrity(db):
    """lock_and_validate_stock and decrement_stock continue to operate reliably."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, stock=6, threshold=5)

    # Lock and decrement 1 unit
    lock_and_validate_stock([(prod.product_id, 1)], db_sess=db.session)
    decrement_stock([(prod.product_id, 1)], db_sess=db.session)
    db.session.commit()

    # Now stock is 5, threshold is 5 -> check_low_stock is True
    status = check_low_stock(prod.product_id, db_sess=db.session)
    assert status["stock_quantity"] == 5
    assert status["is_low_stock"] is True


# =========================================================================
# 5. Deterministic Alias Precedence & Threshold Persistence
# =========================================================================
def test_create_product_canonical_zero_precedence_over_alias(client, app, db):
    """Creation with low_stock_threshold=0 and threshold=5 stores 0."""
    user, artisan = _create_artisan(db)
    cat = Category(name="Cat Zero Precedence", slug="cat-zero-prec")
    db.session.add(cat)
    db.session.commit()

    res = client.post(
        "/api/products",
        json={
            "title": "Zero Threshold Bowl",
            "description": "Handcrafted bowl alerting only at 0 stock",
            "category_id": cat.category_id,
            "price": 320.00,
            "stock_qty": 10,
            "low_stock_threshold": 0,
            "threshold": 5,
        },
        headers=_auth_headers(user),
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["low_stock_threshold"] == 0

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == body["product_id"])
        )
        assert inv.low_stock_threshold == 0


def test_update_product_canonical_zero_precedence_over_alias(client, app, db):
    """Update with low_stock_threshold=0 and threshold=5 stores 0."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Updatable Bowl Zero", stock=10, threshold=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"low_stock_threshold": 0, "threshold": 5},
        headers=_auth_headers(user),
    )
    assert res.status_code == 200
    assert res.get_json()["low_stock_threshold"] == 0

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod.product_id)
        )
        assert inv.low_stock_threshold == 0


def test_alias_only_creation_and_update(client, app, db):
    """Creation and update using only the threshold alias continue to work."""
    user, artisan = _create_artisan(db)
    cat = Category(name="Cat Alias Only", slug="cat-alias-only")
    db.session.add(cat)
    db.session.commit()

    # Create using only 'threshold'
    res = client.post(
        "/api/products",
        json={
            "title": "Alias Only Vase",
            "description": "Handcrafted ceramic vase",
            "category_id": cat.category_id,
            "price": 400.00,
            "stock_qty": 15,
            "threshold": 7,
        },
        headers=_auth_headers(user),
    )
    assert res.status_code == 201
    prod_id = res.get_json()["product_id"]
    assert res.get_json()["low_stock_threshold"] == 7

    # Update using only 'threshold'
    res_up = client.put(
        f"/api/products/{prod_id}",
        json={"threshold": 9},
        headers=_auth_headers(user),
    )
    assert res_up.status_code == 200
    assert res_up.get_json()["low_stock_threshold"] == 9

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod_id)
        )
        assert inv.low_stock_threshold == 9


def test_canonical_positive_precedence_over_alias(client, app, db):
    """Canonical key takes precedence over alias when both are provided."""
    user, artisan = _create_artisan(db)
    cat = Category(name="Cat Canonical Prec", slug="cat-canon-prec")
    db.session.add(cat)
    db.session.commit()

    # Creation: low_stock_threshold=8, threshold=3 -> stores 8
    res = client.post(
        "/api/products",
        json={
            "title": "Precedence Lamp",
            "description": "Handcrafted brass lamp",
            "category_id": cat.category_id,
            "price": 750.00,
            "stock_qty": 20,
            "low_stock_threshold": 8,
            "threshold": 3,
        },
        headers=_auth_headers(user),
    )
    assert res.status_code == 201
    prod_id = res.get_json()["product_id"]
    assert res.get_json()["low_stock_threshold"] == 8

    # Update: low_stock_threshold=12, threshold=2 -> stores 12
    res_up = client.put(
        f"/api/products/{prod_id}",
        json={"low_stock_threshold": 12, "threshold": 2},
        headers=_auth_headers(user),
    )
    assert res_up.status_code == 200
    assert res_up.get_json()["low_stock_threshold"] == 12

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod_id)
        )
        assert inv.low_stock_threshold == 12


def test_partial_update_omitted_threshold_preserves_existing_threshold(client, app, db):
    """Omitting threshold during a partial update preserves the configured threshold."""
    user, artisan = _create_artisan(db)
    prod, _ = _create_product(db, artisan, title="Preserve Thresh Item", stock=15, threshold=8)

    # Partial update: modify only price and stock, omitting threshold
    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 999.00, "stock_qty": 25},
        headers=_auth_headers(user),
    )
    assert res.status_code == 200
    assert res.get_json()["price"] == 999.00
    assert res.get_json()["stock_quantity"] == 25
    assert res.get_json()["low_stock_threshold"] == 8

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod.product_id)
        )
        assert inv.low_stock_threshold == 8
