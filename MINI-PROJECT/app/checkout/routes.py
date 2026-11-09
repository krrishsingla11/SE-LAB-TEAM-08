from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.checkout import history, order_status, service
from app.checkout.service import OrderError
from app.middleware.rbac import role_required

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


def _buyer_id():
    if get_jwt().get("role") != "buyer":
        raise OrderError("FORBIDDEN", "Buyer privilege required", 403)
    return int(get_jwt_identity())


@bp.post("/checkout")
@jwt_required()
def place_order():
    buyer = _buyer_id()
    data = request.get_json(silent=True) or {}
    result = service.checkout(
        buyer,
        data.get("shipping_address"),
        data.get("payment_token"),
        request.headers.get("Idempotency-Key"),
        razorpay_order_id=data.get("razorpay_order_id"),
        razorpay_payment_id=data.get("razorpay_payment_id"),
        razorpay_signature=data.get("razorpay_signature"),
    )
    return jsonify(result), 201


@bp.get("/orders")
@jwt_required()
def my_orders():
    return jsonify({"orders": history.list_orders(_buyer_id())})


@bp.put("/orders/<int:order_id>/status")
@role_required("artisan")
def update_order_status(order_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise OrderError("INVALID_INPUT", "Request body must be a valid JSON object", 400)
    if "status" not in data:
        raise OrderError("MISSING_STATUS", "'status' field is required", 400)
    new_status = data["status"]
    if not isinstance(new_status, str) or not new_status.strip():
        raise OrderError("INVALID_STATUS", "'status' must be a non-empty string", 400)
    result = order_status.transition_order_status(order_id, new_status, user_id)
    return jsonify(result), 200


@bp.get("/seller/orders")
@role_required("artisan")
def seller_orders():
    user_id = int(get_jwt_identity())
    return jsonify({"orders": order_status.list_seller_orders(user_id)}), 200
