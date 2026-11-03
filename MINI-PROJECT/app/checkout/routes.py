from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.checkout import service
from app.checkout.service import OrderError

bp = Blueprint("checkout", __name__, url_prefix="/api")


@bp.errorhandler(OrderError)
def handle_order_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


@bp.post("/checkout")
@jwt_required()
def place_order():
    if get_jwt().get("role") != "buyer":
        raise OrderError("FORBIDDEN", "Buyer privilege required", 403)
    data = request.get_json(silent=True) or {}
    result = service.checkout(
        int(get_jwt_identity()),
        data.get("shipping_address"),
        data.get("payment_token"),
        request.headers.get("Idempotency-Key"),
    )
    return jsonify(result), 201
