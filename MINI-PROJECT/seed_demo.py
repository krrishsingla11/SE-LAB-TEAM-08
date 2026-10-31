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
    return product


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
        category = db.session.scalar(
            db.select(Category).where(Category.slug == "pottery"))
        if category is None:
            category = Category(name="Pottery", slug="pottery")
            db.session.add(category)
            db.session.flush()
        vase = get_product(artisan, category, "Ceramic Vase", 450.00, 20)
        scarf = get_product(artisan, category, "Silk Scarf", 1200.00, 1)
        db.session.commit()
        buyer_token = create_access_token(
            identity=str(buyer.user_id), additional_claims={"role": "buyer"})
        seller_token = create_access_token(
            identity=str(seller.user_id), additional_claims={"role": "artisan"})
        print("Ceramic Vase id:", vase.product_id, "(stock 20, price 450)")
        print("Silk Scarf id:  ", scarf.product_id, "(stock 1, price 1200)")
        print("set BUYER_TOKEN=" + buyer_token)
        print("set ARTISAN_TOKEN=" + seller_token)


if __name__ == "__main__":
    main()
