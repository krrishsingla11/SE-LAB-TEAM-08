"""Seller routes (OMH-F-016 / SE8-33)."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity

from app.middleware.rbac import role_required
from app.seller import service
from app.seller.service import SellerError

bp = Blueprint("seller", __name__, url_prefix="/api")


@bp.errorhandler(SellerError)
def handle_seller_error(e):
    return jsonify({
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), e.status


@bp.get("/seller/dashboard")
@role_required("artisan")
def seller_dashboard():
    user_id = int(get_jwt_identity())
    result = service.get_seller_dashboard(user_id)
    return jsonify(result), 200


@bp.get("/seller/products")
@role_required("artisan")
def seller_products():
    user_id = int(get_jwt_identity())
    return jsonify({"products": service.list_seller_products(user_id)}), 200
