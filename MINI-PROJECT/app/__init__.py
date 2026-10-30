from datetime import datetime, timezone
import os
import time

from flask import Flask, jsonify
from sqlalchemy import text

from app.extensions import db, jwt


def _register_jwt_callbacks(jwt_manager):
    """Register custom JWTManager error callbacks to enforce consistent HTTP 401 errors."""
    if getattr(jwt_manager, "_custom_callbacks_registered", False):
        return

    @jwt_manager.unauthorized_loader
    def unauthorized_callback(error_string):
        return jsonify({
            "error": "UNAUTHORIZED",
            "message": error_string or "Missing authorization header",
            "status_code": 401,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 401

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify({
            "error": "INVALID_TOKEN",
            "message": error_string or "Signature verification failed",
            "status_code": 401,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 401

    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "TOKEN_EXPIRED",
            "message": "Token has expired",
            "status_code": 401,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 401

    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "TOKEN_REVOKED",
            "message": "Token has been revoked",
            "status_code": 401,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 401

    @jwt_manager.needs_fresh_token_loader
    def needs_fresh_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "FRESH_TOKEN_REQUIRED",
            "message": "Fresh token required",
            "status_code": 401,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 401

    jwt_manager._custom_callbacks_registered = True


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
    _register_jwt_callbacks(jwt)

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
