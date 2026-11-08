import threading

from app.checkout.service import OrderError
from app.extensions import db
from app.models import Artisan, Order, OrderItem, Product

VALID_STATUSES = {"Pending", "Processing", "Shipped", "Delivered"}
ALLOWED_TRANSITIONS = {
    "Pending": "Processing",
    "Processing": "Shipped",
    "Shipped": "Delivered",
}

_order_status_lock = threading.Lock()


def transition_order_status(order_id, new_status, artisan_user_id):
    """Transition an order fulfillment status along the allowed lifecycle:
    Pending -> Processing -> Shipped -> Delivered.

    Acquires a row lock on the order, confirms artisan ownership of at least
    one order item, validates the lifecycle transition, and commits atomically.
    """
    if not isinstance(order_id, int):
        raise OrderError("INVALID_INPUT", "order_id must be an integer", 400)
    if not isinstance(artisan_user_id, int):
        raise OrderError("FORBIDDEN", "Artisan privilege required", 403)

    with _order_status_lock:
        try:
            order = db.session.scalar(
                db.select(Order)
                .where(Order.order_id == order_id)
                .with_for_update()
            )
            if order is None:
                raise OrderError("ORDER_NOT_FOUND", "Order not found", 404)

            is_owner = db.session.scalar(
                db.select(OrderItem.order_id)
                .join(Product, Product.product_id == OrderItem.product_id)
                .join(Artisan, Artisan.artisan_id == Product.artisan_id)
                .where(
                    OrderItem.order_id == order.order_id,
                    Artisan.user_id == artisan_user_id,
                )
                .limit(1)
            )
            if not is_owner:
                raise OrderError("FORBIDDEN", "Artisan does not own items in this order", 403)

            if not isinstance(new_status, str) or not new_status.strip():
                raise OrderError("INVALID_STATUS", "'status' must be a non-empty string", 400)

            if new_status not in VALID_STATUSES:
                raise OrderError("INVALID_STATUS", f"Invalid status: '{new_status}'", 400)

            allowed_next = ALLOWED_TRANSITIONS.get(order.status)
            if allowed_next != new_status:
                raise OrderError(
                    "INVALID_TRANSITION",
                    f"Cannot transition order status from '{order.status}' to '{new_status}'",
                    400,
                )

            order.status = new_status
            db.session.commit()
            return {"order_id": order.order_id, "status": order.status}
        except Exception:
            db.session.rollback()
            raise


def list_seller_orders(artisan_user_id):
    """List incoming orders containing products owned by the authenticated artisan.
    Only returns line items belonging to this artisan to avoid data leakage.
    """
    if not isinstance(artisan_user_id, int):
        raise OrderError("FORBIDDEN", "Artisan privilege required", 403)

    artisan = db.session.scalar(
        db.select(Artisan).where(Artisan.user_id == artisan_user_id)
    )
    if artisan is None:
        return []

    orders = db.session.scalars(
        db.select(Order)
        .join(OrderItem, OrderItem.order_id == Order.order_id)
        .join(Product, Product.product_id == OrderItem.product_id)
        .where(Product.artisan_id == artisan.artisan_id)
        .distinct()
        .order_by(Order.order_id.desc())
    ).all()

    result = []
    for order in orders:
        rows = db.session.execute(
            db.select(OrderItem, Product.title)
            .join(Product, Product.product_id == OrderItem.product_id)
            .where(
                OrderItem.order_id == order.order_id,
                Product.artisan_id == artisan.artisan_id,
            )
            .order_by(OrderItem.order_item_id)
        ).all()

        items = [
            {
                "product_id": item.product_id,
                "title": title,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "line_total": round(float(item.unit_price) * item.quantity, 2),
            }
            for item, title in rows
        ]
        artisan_total = round(sum(i["line_total"] for i in items), 2)
        created = getattr(order, "created_at", None)
        result.append({
            "order_id": order.order_id,
            "status": order.status,
            "created_at": created.isoformat() if created else None,
            "shipping_address": order.shipping_address,
            "total": artisan_total,
            "items": items,
        })
    return result
