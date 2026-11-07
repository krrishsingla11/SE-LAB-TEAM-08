from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.cart.service import _cart
from app.extensions import db
from app.models import CartItem, PaymentAttempt, Product
from app.payment import service
from app.payment.gateway import (
    MockGateway,
    PaymentError,
    RazorpayGateway,
    rupees_to_paise,
)
from app.payment.reconciliation import reconcile_all_pending, reconcile_payment_attempt

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


def _buyer_id():
    if get_jwt().get("role") != "buyer":
        raise PaymentError("FORBIDDEN", "Buyer privilege required", 403)
    return int(get_jwt_identity())


def compute_cart_hash(cart_id, lines, prices):
    """Compute deterministic SHA-256 hash of cart lines and current database prices."""
    sorted_lines = sorted(lines, key=lambda item_line: item_line.product_id)
    parts = []
    total = Decimal("0.00")
    for line in sorted_lines:
        price = Decimal(str(prices[line.product_id]))
        qty = line.quantity
        line_total = (price * Decimal(qty)).quantize(Decimal("0.01"))
        total += line_total
        parts.append(f"{line.product_id}:{qty}:{price:.2f}")
    payload = f"{cart_id}|{';'.join(parts)}|{total:.2f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), total


@bp.post("/charge")
@jwt_required()
def charge():
    _buyer_id()
    data = request.get_json(silent=True) or {}
    idem_key = request.headers.get("Idempotency-Key")
    result = service.capture_charge(
        data.get("amount"), data.get("payment_token"), idem_key)
    return jsonify(result), 201


@bp.post("/razorpay-order")
@jwt_required()
def create_razorpay_order():
    buyer_id = _buyer_id()

    # 1. Lock/fetch cart with concurrency protection
    cart = _cart(buyer_id, for_update=True)
    if cart is None:
        raise PaymentError("CART_EMPTY", "Your cart is empty", 400)

    lines = db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id)
    ).all()
    if not lines:
        db.session.rollback()
        raise PaymentError("CART_EMPTY", "Your cart is empty", 400)

    # 2. Calculate current prices from database
    prices = {}
    for line in lines:
        product = db.session.get(Product, line.product_id)
        if product is None or not product.is_active:
            db.session.rollback()
            raise PaymentError(
                "PRODUCT_UNAVAILABLE",
                "A product in your cart is no longer available",
                400,
            )
        prices[line.product_id] = Decimal(str(product.price))

    cart_hash, total_decimal = compute_cart_hash(cart.cart_id, lines, prices)
    total_paise = rupees_to_paise(total_decimal)

    # 3. Check for existing active attempt within 15-minute window
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    existing_attempt = db.session.scalar(
        db.select(PaymentAttempt)
        .where(
            PaymentAttempt.buyer_id == buyer_id,
            PaymentAttempt.cart_id == cart.cart_id,
            PaymentAttempt.cart_hash == cart_hash,
            PaymentAttempt.amount == total_decimal,
            PaymentAttempt.status.in_(["created", "callback_received"]),
            PaymentAttempt.created_at >= cutoff,
        )
        .order_by(PaymentAttempt.created_at.desc())
    )

    gateway = service.get_gateway()
    key_id = getattr(gateway, "key_id", "rzp_test_mockkey")

    if existing_attempt:
        db.session.commit()
        return jsonify({
            "razorpay_order_id": existing_attempt.razorpay_order_id,
            "amount": rupees_to_paise(existing_attempt.amount),
            "currency": existing_attempt.currency,
            "key_id": key_id,
            "attempt_id": existing_attempt.attempt_id,
        }), 200

    # 4. Create new Razorpay order
    try:
        if isinstance(gateway, RazorpayGateway):
            receipt_id = f"rcpt_{cart.cart_id}_{uuid.uuid4().hex[:8]}"
            order_payload = {
                "amount": total_paise,
                "currency": "INR",
                "receipt": receipt_id,
                "payment": {
                    "capture": "automatic",
                    "capture_options": {
                        "automatic_expiry_period": 12,
                        "refund_speed": "optimum",
                    },
                },
                "notes": {
                    "cart_id": str(cart.cart_id),
                    "buyer_id": str(buyer_id),
                },
            }
            order_res = gateway.client.order.create(
                data=order_payload, timeout=gateway.timeout
            )
            razorpay_order_id = str(order_res["id"]).strip()
            key_id = gateway.key_id
        elif isinstance(gateway, MockGateway):
            razorpay_order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
            key_id = "rzp_test_mockkey"
        else:
            razorpay_order_id = f"order_stub_{uuid.uuid4().hex[:14]}"
            key_id = getattr(gateway, "key_id", "rzp_test_stubkey")

        attempt = PaymentAttempt(
            buyer_id=buyer_id,
            cart_id=cart.cart_id,
            amount=total_decimal,
            currency="INR",
            cart_hash=cart_hash,
            razorpay_order_id=razorpay_order_id,
            status="created",
        )
        db.session.add(attempt)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        "razorpay_order_id": razorpay_order_id,
        "amount": total_paise,
        "currency": "INR",
        "key_id": key_id,
        "attempt_id": attempt.attempt_id,
    }), 201


@bp.post("/reconcile/<int:attempt_id>")
@jwt_required()
def trigger_reconciliation(attempt_id):
    jwt_claims = get_jwt()
    role = jwt_claims.get("role")
    if role not in ("admin", "buyer"):
        raise PaymentError("FORBIDDEN", "Unauthorized", 403)

    caller_buyer_id = int(get_jwt_identity()) if role == "buyer" else None
    try:
        result = reconcile_payment_attempt(attempt_id, buyer_id=caller_buyer_id)
    except PermissionError as err:
        raise PaymentError("FORBIDDEN", str(err), 403)
    except ValueError as err:
        raise PaymentError("NOT_FOUND", str(err), 404)
    return jsonify(result), 200


@bp.post("/reconcile")
@jwt_required()
def trigger_bulk_reconciliation():
    if get_jwt().get("role") != "admin":
        raise PaymentError("FORBIDDEN", "Admin privilege required for bulk reconciliation", 403)
    results = reconcile_all_pending()
    return jsonify({"results": results}), 200
