import os
import time

from flask import Flask, jsonify
from sqlalchemy import text

from app.extensions import db, jwt


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@db:5432/marketplace",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv(
            "JWT_SECRET_KEY", "dev-only-change-me"
        ),
        START_TIME=time.monotonic(),
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    jwt.init_app(app)

    # Register models with SQLAlchemy metadata.
    from app.models import (
        User,
        Artisan,
        Category,
        Product,
        ProductImage,
        Inventory,
        Cart,
        CartItem,
        Order,
        OrderItem,
        Payment,
        Invoice,
    )

    # Keep references available for migration and model discovery.
    _ = (
        User, Artisan, Category, Product, ProductImage, Inventory,
        Cart, CartItem, Order, OrderItem, Payment, Invoice,
    )

    from app.cart import cart_bp
    from app.search import catalog_bp
    from app.auth import auth_bp
    from app.payment import payment_bp

    app.register_blueprint(cart_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(payment_bp)

    @app.get("/api/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            database_status = "connected"
            status_code = 200
            app_status = "ok"
        except Exception:
            db.session.rollback()
            database_status = "disconnected"
            status_code = 503
            app_status = "degraded"

        return jsonify(
            status=app_status,
            database=database_status,
            uptime_seconds=round(
                time.monotonic() - app.config["START_TIME"], 2
            ),
        ), status_code

    return app