from app.extensions import db
from app.models import Inventory, Product


class OutOfStock(Exception):
    def __init__(self, title, available):
        super().__init__(title)
        self.title = title
        self.available = available


def lock_and_validate_stock(items, db_sess=None):
    session = db_sess or db.session
    for product_id, qty in sorted(items):
        inv = session.scalar(
            db.select(Inventory)
            .where(Inventory.product_id == product_id)
            .with_for_update()
        )
        available = inv.stock_quantity if inv else 0
        if available < qty:
            product = session.get(Product, product_id)
            title = product.title if product else f"#{product_id}"
            raise OutOfStock(title, available)


def decrement_stock(items, db_sess=None):
    session = db_sess or db.session
    for product_id, qty in items:
        result = session.execute(
            db.update(Inventory)
            .where(
                Inventory.product_id == product_id,
                Inventory.stock_quantity >= qty,
            )
            .values(stock_quantity=Inventory.stock_quantity - qty)
        )
        if result.rowcount != 1:
            raise OutOfStock(f"#{product_id}", 0)


def check_low_stock(product_id, db_sess=None):
    """Check if a product is at or below its configured low-stock threshold (OMH-F-016).

    Args:
        product_id: Product ID to inspect.
        db_sess: Optional SQLAlchemy session; defaults to db.session.

    Returns:
        dict | None: Dictionary with stock details and low-stock boolean,
                     or None if no inventory record exists for the product.
    """
    session = db_sess or db.session
    inv = session.scalar(
        db.select(Inventory).where(Inventory.product_id == product_id)
    )
    if inv is None:
        return None
    return {
        "product_id": product_id,
        "stock_quantity": inv.stock_quantity,
        "threshold": inv.low_stock_threshold,
        "is_low_stock": inv.stock_quantity <= inv.low_stock_threshold,
    }
