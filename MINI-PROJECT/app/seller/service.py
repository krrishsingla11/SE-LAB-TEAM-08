"""Seller dashboard service (OMH-F-016 / SE8-33)."""
from app.extensions import db
from app.models import Artisan, Inventory, Product


class SellerError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def get_seller_dashboard(user_id: int) -> dict:
    """Retrieve seller dashboard data including low-stock alerts (OMH-F-016).

    Args:
        user_id: Authenticated user ID (must correspond to an Artisan profile).

    Returns:
        dict: JSON-serializable dashboard payload conforming to frontend contract:
              {"low_stock": [{"product_id": int, "title": str,
                              "stock_quantity": int, "threshold": int}]}
    """
    artisan = db.session.scalar(
        db.select(Artisan).where(Artisan.user_id == user_id)
    )
    if artisan is None:
        raise SellerError("FORBIDDEN", "Artisan profile required", 403)

    # Bulk query active products owned by this artisan where stock is at or below threshold
    stmt = (
        db.select(
            Product.product_id,
            Product.title,
            Inventory.stock_quantity,
            Inventory.low_stock_threshold,
        )
        .join(Inventory, Inventory.product_id == Product.product_id)
        .where(
            Product.artisan_id == artisan.artisan_id,
            Product.is_active.is_(True),
            Inventory.stock_quantity <= Inventory.low_stock_threshold,
        )
        .order_by(Inventory.stock_quantity.asc(), Product.product_id.asc())
    )

    rows = db.session.execute(stmt).all()
    low_stock = [
        {
            "product_id": r.product_id,
            "title": r.title,
            "stock_quantity": r.stock_quantity,
            "threshold": r.low_stock_threshold,
        }
        for r in rows
    ]

    return {"low_stock": low_stock}
