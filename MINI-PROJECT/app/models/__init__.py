from datetime import datetime, timezone

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(
        db.Enum("buyer", "artisan", "admin", name="user_role"),
        nullable=False,
        default="buyer",
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now
    )


class Artisan(db.Model):
    __tablename__ = "artisans"

    artisan_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"),
        unique=True, nullable=False
    )
    shop_name = db.Column(db.String(150), nullable=False)
    bio = db.Column(db.Text)
    banner_url = db.Column(db.String(255))


class Category(db.Model):
    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)


class Product(db.Model):
    __tablename__ = "products"

    product_id = db.Column(db.Integer, primary_key=True)
    artisan_id = db.Column(
        db.Integer, db.ForeignKey("artisans.artisan_id"), nullable=False
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.category_id"), nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class ProductImage(db.Model):
    __tablename__ = "product_images"

    image_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.product_id"), nullable=False
    )
    image_url = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now
    )


class Inventory(db.Model):
    __tablename__ = "inventory"

    inventory_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.product_id"),
        unique=True,
        nullable=False,
    )
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    last_updated = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class Cart(db.Model):
    __tablename__ = "carts"

    cart_id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"),
        unique=True, nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class CartItem(db.Model):
    __tablename__ = "cart_items"

    item_id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(
        db.Integer, db.ForeignKey("carts.cart_id"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.product_id"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)


class Order(db.Model):
    __tablename__ = "orders"

    order_id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False
    )
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(
        db.Enum(
            "Pending", "Processing", "Shipped", "Delivered",
            name="order_fulfillment_status",
        ),
        nullable=False,
        default="Pending",
    )
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    order_item_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.order_id"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.product_id"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)


class Payment(db.Model):
    __tablename__ = "payments"

    payment_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.order_id"),
        unique=True,
        nullable=False,
    )
    transaction_ref = db.Column(db.String(100))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(
        db.Enum(
            "pending", "authorized", "captured", "failed", "refunded",
            name="payment_outcome_status",
        ),
        nullable=False,
        default="pending",
    )
    paid_at = db.Column(db.DateTime(timezone=True))


class Invoice(db.Model):
    __tablename__ = "invoices"

    invoice_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.order_id"),
        unique=True,
        nullable=False,
    )
    invoice_number = db.Column(
        db.String(50), unique=True, nullable=False
    )
    file_path = db.Column(db.String(255), nullable=False)
    issued_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now
    )
