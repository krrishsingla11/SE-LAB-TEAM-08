import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db
from app.models import Artisan, Category, Inventory, Product, User

PASSWORD = b"Demo@12345"


def get_user(email, name, role):
    user = db.session.scalar(db.select(User).where(User.email == email))
    if user is None:
        hashed = bcrypt.hashpw(PASSWORD, bcrypt.gensalt(12)).decode()
        user = User(email=email, password_hash=hashed, full_name=name, role=role)
        db.session.add(user)
        db.session.flush()
    return user


def get_category(name, slug):
    category = db.session.scalar(db.select(Category).where(Category.slug == slug))
    if category is None:
        category = Category(name=name, slug=slug)
        db.session.add(category)
        db.session.flush()
    return category


def get_product(artisan, category, title, price, stock):
    product = db.session.scalar(db.select(Product).where(Product.title == title))
    if product is None:
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
        db.session.add(Inventory(
            product_id=product.product_id,
            stock_quantity=stock,
            low_stock_threshold=5,
        ))
    elif product.category_id != category.category_id:
        product.category_id = category.category_id  # fix products seeded under the wrong category
    return product


# (category, slug) -> [(title, price, stock)]. Vase and Scarf stay first (ids 1 and 2).
CATALOG = [
    (("Pottery", "pottery"), [
        ("Ceramic Vase", 450.00, 20), ("Terracotta Planter", 450.00, 25)]),
    (("Textiles", "textiles"), [
        ("Silk Scarf", 1200.00, 1), ("Block-Printed Table Runner", 980.00, 8)]),
    (("Woodwork", "woodwork"), [
        ("Carved Teak Coaster Set", 640.00, 0), ("Wooden Spice Box", 1500.00, 9)]),
    (("Metalwork", "metalwork"), [
        ("Brass Diya Lamp", 720.00, 4), ("Copper Water Bottle", 1100.00, 15)]),
    (("Jewellery", "jewellery"), [
        ("Beaded Necklace", 950.00, 10), ("Silver Jhumka Earrings", 1800.00, 6)]),
]


def main():
    app = create_app()
    with app.app_context():
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            db.create_all()
        buyer = get_user("buyer@demo.test", "Demo Buyer", "buyer")
        seller = get_user("artisan@demo.test", "Demo Artisan", "artisan")
        artisan = db.session.scalar(
            db.select(Artisan).where(Artisan.user_id == seller.user_id))
        if artisan is None:
            artisan = Artisan(user_id=seller.user_id, shop_name="Demo Crafts")
            db.session.add(artisan)
            db.session.flush()
        products = {}
        for (cat_name, cat_slug), items in CATALOG:
            category = get_category(cat_name, cat_slug)
            for title, price, stock in items:
                products[title] = get_product(artisan, category, title, price, stock)
        vase = products["Ceramic Vase"]
        scarf = products["Silk Scarf"]
        db.session.commit()
        buyer_token = create_access_token(
            identity=str(buyer.user_id), additional_claims={"role": "buyer"})
        seller_token = create_access_token(
            identity=str(seller.user_id), additional_claims={"role": "artisan"})
        print("Ceramic Vase id:", vase.product_id, "(stock 20, price 450)")
        print("Silk Scarf id:  ", scarf.product_id, "(stock 1, price 1200)")
        print("Categories:", len(CATALOG), "| products:", len(products))
        print("set BUYER_TOKEN=" + buyer_token)
        print("set ARTISAN_TOKEN=" + seller_token)


if __name__ == "__main__":
    main()
