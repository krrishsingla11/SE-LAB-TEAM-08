"""Cart & pre-checkout tests - STP section 13.3 (TC-CART-01..03, TC-CHK-01).

Note: the app has no /api/checkout route yet. The stock check (F-009) lives in
the cart service, so TC-CHK-01 is tested at cart level (see its docstring).
"""
import uuid

import pytest

from app.extensions import db
from app.models import Artisan, CartItem, Category, Inventory, Product, User

PASSWORD = "StrongP@ss123"


def _headers(client, role="buyer"):
    email = f"cart_{uuid.uuid4().hex[:8]}@pes.edu"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Cart Tester", "role": role},
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.get_json()
    return {"Authorization": f"Bearer {login.get_json()['token']}"}


@pytest.fixture
def buyer_headers(client):
    return _headers(client)


def _make_product(title, price, stock):
    """Insert an artisan, a category, a product and its stock; return the product id."""
    tag = uuid.uuid4().hex[:8]
    seller = User(
        email=f"seller_{tag}@pes.edu",
        password_hash="not-a-real-hash",
        full_name="Test Seller",
        role="artisan",
    )
    db.session.add(seller)
    db.session.flush()
    artisan = Artisan(user_id=seller.user_id, shop_name=f"Shop {tag}")
    category = Category(name=f"Category {tag}", slug=f"cat-{tag}")
    db.session.add_all([artisan, category])
    db.session.flush()
    product = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description="Handmade " + title.lower(),
        price=price,
        is_active=True,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(
        Inventory(product_id=product.product_id, stock_quantity=stock, low_stock_threshold=5)
    )
    db.session.commit()
    return product.product_id


def _add(client, headers, product_id, quantity):
    return client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": quantity},
        headers=headers,
    )


def test_tc_cart_01_add_item_and_update_quantity(client, buyer_headers):
    """TC-CART-01 (High) - OMH-F-008
    Steps:    POST /api/cart/items qty=2; then PUT /api/cart/items/{id} qty=3.
    Expected: HTTP 200; subtotal recalculates to 3 * unit_price; saved in DB.
    """
    product_id = _make_product("Ceramic Vase", 450.00, 20)

    added = _add(client, buyer_headers, product_id, 2)
    assert added.status_code == 200, added.get_json()
    assert added.get_json()["subtotal"] == 900.0

    updated = client.put(
        f"/api/cart/items/{product_id}", json={"quantity": 3}, headers=buyer_headers
    )
    assert updated.status_code == 200, updated.get_json()
    body = updated.get_json()
    assert body["subtotal"] == 1350.0
    assert body["cart"][0]["quantity"] == 3
    assert body["cart"][0]["unit_price"] == 450.0

    saved = db.session.scalar(db.select(CartItem).where(CartItem.product_id == product_id))
    assert saved.quantity == 3


def test_tc_cart_02_add_quantity_exceeding_stock(client, buyer_headers):
    """TC-CART-02 (High) - OMH-F-008
    Steps:    Product stock=5; POST /api/cart/items qty=10.
    Expected: HTTP 400; error 'Requested quantity exceeds available inventory (5)'.
    """
    product_id = _make_product("Silk Scarf", 1200.00, 5)

    resp = _add(client, buyer_headers, product_id, 10)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "INSUFFICIENT_STOCK"
    assert body["message"] == "Requested quantity exceeds available inventory (5)"

    cart = client.get("/api/cart", headers=buyer_headers).get_json()
    assert cart["cart"] == []


def test_tc_cart_03_remove_last_item(client, buyer_headers):
    """TC-CART-03 (Medium) - OMH-F-008
    Steps:    DELETE /api/cart/items/{id}; then GET /api/cart.
    Expected: HTTP 200; items array empty; subtotal 0.00.
    """
    product_id = _make_product("Clay Bowl", 300.00, 10)
    assert _add(client, buyer_headers, product_id, 1).status_code == 200

    removed = client.delete(f"/api/cart/items/{product_id}", headers=buyer_headers)
    assert removed.status_code == 200

    cart = client.get("/api/cart", headers=buyer_headers)
    assert cart.status_code == 200
    assert cart.get_json() == {"cart": [], "subtotal": 0.0}


def test_tc_chk_01_checkout_with_depleted_stock(client, buyer_headers):
    """TC-CHK-01 (High) - OMH-F-009
    Steps:    Stock is 0 (never had stock, or sold out after the item was added);
              try to add or keep the quantity.
    Expected: HTTP 400 'Requested quantity exceeds available inventory (0)'; the cart
              is not changed, so nothing can go to payment.
    Note:     the STP uses POST /api/checkout, which does not exist yet; the error
              also does not name the product.
    """
    sold_out = _make_product("Sold Out Lamp", 800.00, 0)
    first = _add(client, buyer_headers, sold_out, 1)
    assert first.status_code == 400
    assert first.get_json()["message"] == "Requested quantity exceeds available inventory (0)"

    product_id = _make_product("Wooden Tray", 250.00, 5)
    assert _add(client, buyer_headers, product_id, 2).status_code == 200

    inventory = db.session.scalar(
        db.select(Inventory).where(Inventory.product_id == product_id)
    )
    inventory.stock_quantity = 0  # someone else bought the last items
    db.session.commit()

    again = client.put(
        f"/api/cart/items/{product_id}", json={"quantity": 2}, headers=buyer_headers
    )
    assert again.status_code == 400
    assert again.get_json()["message"] == "Requested quantity exceeds available inventory (0)"

    cart = client.get("/api/cart", headers=buyer_headers).get_json()
    assert cart["cart"][0]["quantity"] == 2


def test_cart_requires_authentication(client):
    assert client.get("/api/cart").status_code == 401


def test_cart_is_buyer_only(client):
    artisan_headers = _headers(client, role="artisan")
    resp = client.get("/api/cart", headers=artisan_headers)
    assert resp.status_code == 403
    assert resp.get_json()["message"] == "Buyer privilege required"


def test_cart_rejects_invalid_quantity(client, buyer_headers):
    product_id = _make_product("Glass Jar", 150.00, 10)
    resp = _add(client, buyer_headers, product_id, 0)
    assert resp.status_code == 422
