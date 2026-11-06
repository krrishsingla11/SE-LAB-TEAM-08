from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.checkout import history, service
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
