import logging

from app.checkout.stock import (
    OutOfStock,
    decrement_stock,
    lock_and_validate_stock,
)
from app.extensions import db
from app.models import Cart, CartItem, Order, OrderItem, Payment, Product
from app.payment import service as payment_service
from app.payment.gateway import PaymentError

log = logging.getLogger(__name__)

MAX_ADDRESS_LENGTH = 500


class OrderError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _clean_address(address):
    if not isinstance(address, str) or not address.strip():
        raise OrderError("INVALID_ADDRESS", "shipping_address is required", 422)
    if len(address.strip()) > MAX_ADDRESS_LENGTH:
        raise OrderError("INVALID_ADDRESS", "shipping_address is too long", 422)
    return address.strip()


def _cart_lines(buyer_id):
    cart = db.session.scalar(db.select(Cart).where(Cart.buyer_id == buyer_id))
    if cart is None:
        return []
    return db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id)
    ).all()


def _current_prices(lines):
    # Prices always come from the database, never from the client.
    prices = {}
    for line in lines:
        product = db.session.get(Product, line.product_id)
        if product is None or not product.is_active:
            raise OrderError(
                "PRODUCT_UNAVAILABLE",
                "A product in your cart is no longer available", 400)
        prices[line.product_id] = round(float(product.price), 2)
    return prices


def _refund(charge, reason):
    if charge is not None:
        payment_service.void_or_refund_charge(charge["transaction_ref"], reason)
        log.error("Charge %s refunded: %s", charge["transaction_ref"], reason)


def _save_order(buyer_id, address, lines, prices, total, charge):
    order = Order(
        buyer_id=buyer_id,
        total_amount=total,
        status="Processing",
        shipping_address=address,
    )
    db.session.add(order)
    db.session.flush()
    for line in lines:
        db.session.add(OrderItem(
            order_id=order.order_id,
            product_id=line.product_id,
            quantity=line.quantity,
            unit_price=prices[line.product_id],
        ))
        db.session.delete(line)
    db.session.add(Payment(
        order_id=order.order_id,
        transaction_ref=charge["transaction_ref"],
        amount=total,
        payment_status="captured",
    ))
    return order


def _summary(order, charge):
    return {
        "order_id": order.order_id,
        "status": order.status,
        "payment_status": "captured",
        "total": float(order.total_amount),
        "transaction_ref": charge["transaction_ref"],
        "invoice_url": None,  # filled in by the invoice ticket (SE8-34)
    }


def checkout(buyer_id, shipping_address, payment_token, idem_key=None):
    address = _clean_address(shipping_address)
    lines = _cart_lines(buyer_id)
    if not lines:
        raise OrderError("CART_EMPTY", "Your cart is empty", 400)
    items = [(line.product_id, line.quantity) for line in lines]
    charge = None
    try:
        prices = _current_prices(lines)
        total = round(sum(prices[pid] * qty for pid, qty in items), 2)
        lock_and_validate_stock(items)
        charge = payment_service.capture_charge(total, payment_token, idem_key)
        decrement_stock(items)
        order = _save_order(buyer_id, address, lines, prices, total, charge)
        db.session.commit()
    except OutOfStock as err:
        db.session.rollback()
        _refund(charge, "stock ran out during checkout")
        raise OrderError(
            "INSUFFICIENT_STOCK",
            f"'{err.title}' only has {err.available} unit(s) available", 400,
        ) from err
    except PaymentError as err:
        db.session.rollback()
        raise OrderError(err.code, err.message, err.status) from err
    except OrderError:
        db.session.rollback()
        raise
    except Exception as err:
        db.session.rollback()
        _refund(charge, "order could not be saved")
        log.exception("Checkout failed")
        raise OrderError(
            "ORDER_FAILED",
            "The order could not be completed. Please try again.", 500,
        ) from err
    return _summary(order, charge)
