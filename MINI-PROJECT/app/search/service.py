from sqlalchemy import func, or_

from app.extensions import db
from app.models import Category, Inventory, Product, ProductImage

DEFAULT_PER_PAGE = 12
MAX_PER_PAGE = 50


class SearchError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _like(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _conditions(q, category_id):
    conditions = [Product.is_active.is_(True)]
    if q:
        pattern = _like(q)
        conditions.append(or_(
            Product.title.ilike(pattern, escape="\\"),
            Product.description.ilike(pattern, escape="\\"),
        ))
    if category_id is not None:
        conditions.append(Product.category_id == category_id)
    return conditions


def _primary_images(product_ids):
    if not product_ids:
        return {}
    rows = db.session.execute(
        db.select(ProductImage.product_id, ProductImage.image_url).where(
            ProductImage.product_id.in_(product_ids),
            ProductImage.is_primary.is_(True),
        )
    )
    return {product_id: url for product_id, url in rows}


def _card(product, stock, image_url):
    stock = stock or 0
    return {
        "product_id": product.product_id,
        "title": product.title,
        "description": product.description,
        "price": float(product.price),
        "category_id": product.category_id,
        "artisan_id": product.artisan_id,
        "image_url": image_url,
        "stock_quantity": stock,
        "in_stock": stock > 0,
    }


def search_catalog(q=None, category_id=None, page=1, per_page=DEFAULT_PER_PAGE):
    if page < 1:
        raise SearchError("INVALID_PAGE", "page must be 1 or higher", 422)
    if per_page < 1 or per_page > MAX_PER_PAGE:
        raise SearchError(
            "INVALID_PAGE_SIZE",
            f"per_page must be between 1 and {MAX_PER_PAGE}", 422)
    conditions = _conditions(q, category_id)
    total = db.session.scalar(
        db.select(func.count(Product.product_id)).where(*conditions))
    rows = db.session.execute(
        db.select(Product, Inventory.stock_quantity)
        .outerjoin(Inventory, Inventory.product_id == Product.product_id)
        .where(*conditions)
        .order_by(Product.product_id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    ).all()
    images = _primary_images([product.product_id for product, _ in rows])
    products = [
        _card(product, stock, images.get(product.product_id))
        for product, stock in rows
    ]
    return {"products": products, "total": total,
            "page": page, "per_page": per_page}


def get_product(product_id):
    row = db.session.execute(
        db.select(Product, Inventory.stock_quantity)
        .outerjoin(Inventory, Inventory.product_id == Product.product_id)
        .where(Product.product_id == product_id, Product.is_active.is_(True))
    ).first()
    if row is None:
        raise SearchError("NOT_FOUND", "Product not found", 404)
    product, stock = row
    images = db.session.scalars(
        db.select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.is_primary.desc())
    ).all()
    data = _card(product, stock, None)
    data["images"] = [
        {"url": image.image_url, "is_primary": bool(image.is_primary)}
        for image in images
    ]
    data["image_url"] = data["images"][0]["url"] if data["images"] else None
    return data


def list_categories():
    rows = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    return [
        {"category_id": c.category_id, "name": c.name, "slug": c.slug}
        for c in rows
    ]
