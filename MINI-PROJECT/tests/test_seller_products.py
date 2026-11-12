"""Tests for GET /api/seller/products: the artisan's full inventory with categories."""
from decimal import Decimal

from flask_jwt_extended import create_access_token

from app.models import Artisan, Category, Inventory, Product, User


def _user(db, email, role):
    user = User(email=email, password_hash="x", full_name=email, role=role)
    db.session.add(user)
    db.session.flush()
    return user


def _artisan(db, email):
    user = _user(db, email, "artisan")
    artisan = Artisan(user_id=user.user_id, shop_name="Shop " + email)
    db.session.add(artisan)
    db.session.flush()
    return user, artisan


def _category(db, name):
    category = Category(name=name, slug=name.lower())
    db.session.add(category)
    db.session.flush()
    return category


def _product(db, artisan, category, title, stock, active=True):
    product = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description=title,
        price=Decimal("100.00"),
        is_active=active,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(Inventory(product_id=product.product_id, stock_quantity=stock,
                             low_stock_threshold=5))
    return product


def _headers(user):
    token = create_access_token(identity=str(user.user_id),
                                additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_lists_all_own_products_with_categories_sorted(client, db):
    user, artisan = _artisan(db, "a@x.test")
    _, other = _artisan(db, "b@x.test")
    pottery, textiles = _category(db, "Pottery"), _category(db, "Textiles")
    _product(db, artisan, textiles, "Silk Scarf", 1)
    _product(db, artisan, pottery, "Vase", 20)
    _product(db, artisan, pottery, "Bowl", 0)
    _product(db, artisan, pottery, "Hidden", 5, active=False)
    _product(db, other, pottery, "Not Mine", 9)
    db.session.commit()

    res = client.get("/api/seller/products", headers=_headers(user))
    assert res.status_code == 200
    rows = res.get_json()["products"]
    assert [(r["category"], r["title"]) for r in rows] == [
        ("Pottery", "Bowl"), ("Pottery", "Vase"), ("Textiles", "Silk Scarf")]
    bowl = rows[0]
    assert bowl["stock_quantity"] == 0 and bowl["in_stock"] is False
    assert rows[2]["stock_quantity"] == 1 and rows[2]["threshold"] == 5


def test_buyer_is_forbidden(client, db):
    buyer = _user(db, "buyer@x.test", "buyer")
    db.session.commit()
    res = client.get("/api/seller/products", headers=_headers(buyer))
    assert res.status_code == 403


def test_requires_login(client):
    assert client.get("/api/seller/products").status_code in (401, 422)
