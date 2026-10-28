from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.cart import service
from app.cart.service import CartError

bp = Blueprint("cart", __name__, url_prefix="/api/cart")


def _buyer_id():
    if get_jwt().get("role") != "buyer":
        raise CartError("FORBIDDEN", "Buyer privilege required", 403)
    return int(get_jwt_identity())


def _int(data, key, default=None):
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CartError("INVALID_INPUT", f"'{key}' must be a whole number", 422)
    return value


@bp.errorhandler(CartError)
def handle_cart_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


@bp.get("")
@jwt_required()
def view_cart():
    return jsonify(service.get_cart(_buyer_id()))


@bp.post("/items")
@jwt_required()
def add():
    buyer = _buyer_id()
    data = request.get_json(silent=True) or {}
    product_id = _int(data, "product_id")
    quantity = _int(data, "quantity", 1)
    return jsonify(service.add_item(buyer, product_id, quantity))


@bp.put("/items/<int:product_id>")
@jwt_required()
def update(product_id):
    buyer = _buyer_id()
    data = request.get_json(silent=True) or {}
    return jsonify(service.update_qty(buyer, product_id, _int(data, "quantity")))


@bp.delete("/items/<int:product_id>")
@jwt_required()
def remove(product_id):
    return jsonify(service.remove_item(_buyer_id(), product_id))