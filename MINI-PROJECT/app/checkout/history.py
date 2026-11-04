from app.extensions import db
from app.models import Order, OrderItem, Product


def list_orders(buyer_id):
    orders = db.session.scalars(
        db.select(Order).where(Order.buyer_id == buyer_id)
        .order_by(Order.order_id.desc())
    ).all()
    result = []
    for order in orders:
        rows = db.session.execute(
            db.select(OrderItem, Product.title)
            .join(Product, Product.product_id == OrderItem.product_id)
            .where(OrderItem.order_id == order.order_id)
        ).all()
        created = getattr(order, "created_at", None)
        result.append({
            "order_id": order.order_id,
            "status": order.status,
            "total": float(order.total_amount),
            "shipping_address": order.shipping_address,
            "created_at": created.isoformat() if created else None,
            "invoice_url": f"/api/orders/{order.order_id}/invoice",
            "items": [
                {
                    "product_id": item.product_id,
                    "title": title,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                }
                for item, title in rows
            ],
        })
    return result
