from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from app.payment import service
from app.payment.gateway import PaymentError

bp = Blueprint("payment", __name__, url_prefix="/api/payments")


@bp.errorhandler(PaymentError)
def handle_payment_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


@bp.post("/charge")
@jwt_required()
def charge():
    if get_jwt().get("role") != "buyer":
        raise PaymentError("FORBIDDEN", "Buyer privilege required", 403)
    data = request.get_json(silent=True) or {}
    idem_key = request.headers.get("Idempotency-Key")
    result = service.capture_charge(
        data.get("amount"), data.get("payment_token"), idem_key)
    return jsonify(result), 201
