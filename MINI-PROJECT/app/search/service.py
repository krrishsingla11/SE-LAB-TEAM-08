from decimal import Decimal, InvalidOperation
import math
import os
import re
import uuid

from flask import current_app
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Artisan, Category, Inventory, Product, ProductImage

DEFAULT_PER_PAGE = 12
MAX_PER_PAGE = 50


class SearchError(Exception):
    def __init__(self, code, message, status=400, errors=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.errors = errors


def get_upload_folder():
    """Retrieve or initialize the configured image upload directory."""
    folder = current_app.config.get("UPLOAD_FOLDER")
    if not folder:
        folder = os.path.join(
            os.path.dirname(current_app.root_path), "uploads"
        )
    os.makedirs(folder, exist_ok=True)
    return folder


def validate_product_input(data, files):
    """Validate product input fields and uploaded images (OMH-F-005).

    Returns:
        tuple: (title, desc, category_id, price, stock_qty, valid_files)
    Raises:
        SearchError: HTTP 422 if any validation constraints are violated.
    """
    errors = []

    # 1. Title validation (3-200 characters)
    title = data.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        errors.append("Title is required")
        parsed_title = ""
    else:
        parsed_title = title.strip()
        if len(parsed_title) < 3 or len(parsed_title) > 200:
            errors.append("Title must be between 3 and 200 characters")

    # 2. Description validation (non-empty string)
    desc = data.get("description") if data.get("description") is not None else data.get("desc")
    if desc is None or not isinstance(desc, str) or not desc.strip():
        errors.append("Description is required")
        parsed_desc = ""
    else:
        parsed_desc = desc.strip()

    # 3. Category validation (mandatory, must reference existing Category)
    cat_raw = (
        data.get("category_id")
        if data.get("category_id") is not None
        else data.get("category")
    )
    if cat_raw is None or isinstance(cat_raw, bool) or cat_raw == "":
        errors.append("Category is required")
        parsed_cat_id = None
    else:
        try:
            if isinstance(cat_raw, str):
                s = cat_raw.strip()
                if not re.match(r"^-?\d+$", s):
                    raise ValueError
                parsed_cat_id = int(s)
            elif isinstance(cat_raw, int):
                parsed_cat_id = cat_raw
            else:
                raise ValueError

            cat = db.session.get(Category, parsed_cat_id)
            if cat is None:
                errors.append(f"Category with id {parsed_cat_id} does not exist")
        except (ValueError, TypeError):
            errors.append("Category must be a valid integer ID")
            parsed_cat_id = None

    # 4. Price validation (positive decimal > 0.00)
    price_raw = data.get("price")
    if price_raw is None or isinstance(price_raw, bool) or price_raw == "":
        errors.append("Price is required")
        parsed_price = None
    else:
        try:
            if isinstance(price_raw, (int, float)):
                if math.isnan(price_raw) or math.isinf(price_raw):
                    raise ValueError
                parsed_price = round(Decimal(str(price_raw)), 2)
            elif isinstance(price_raw, str):
                s = price_raw.strip().lower()
                if s in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
                    raise ValueError
                parsed_price = round(Decimal(s), 2)
            elif isinstance(price_raw, Decimal):
                if price_raw.is_nan() or price_raw.is_infinite():
                    raise ValueError
                parsed_price = round(price_raw, 2)
            else:
                raise ValueError

            if parsed_price <= Decimal("0.00"):
                errors.append("Price must be greater than zero")
        except (InvalidOperation, ValueError, TypeError):
            errors.append("Price must be a valid positive number")
            parsed_price = None

    # 5. Stock quantity validation (non-negative integer >= 0)
    stock_raw = data.get("stock_qty")
    if stock_raw is None:
        stock_raw = data.get("stock_quantity")
    if stock_raw is None:
        stock_raw = data.get("stock")

    if stock_raw is None or isinstance(stock_raw, bool) or stock_raw == "":
        errors.append("Stock quantity is required")
        parsed_stock = None
    else:
        try:
            if isinstance(stock_raw, str):
                s = stock_raw.strip()
                if not re.match(r"^-?\d+$", s):
                    raise ValueError
                parsed_stock = int(s)
            elif isinstance(stock_raw, int):
                parsed_stock = stock_raw
            else:
                raise ValueError

            if parsed_stock < 0:
                errors.append("Stock quantity cannot be negative")
        except (ValueError, TypeError):
            errors.append("Stock quantity must be a non-negative whole number")
            parsed_stock = None

    # 6. Reject arbitrary user-provided image URLs in JSON
    if "images" in data and isinstance(data["images"], list) and len(data["images"]) > 0:
        errors.append(
            "Image URLs in JSON body are not supported. Upload images via multipart/form-data."
        )

    # 7. Uploaded images validation (max 5 files, JPEG/PNG/WebP, max 5 MB each)
    valid_files = [
        f for f in (files or [])
        if f and getattr(f, "filename", None) and f.filename.strip()
    ]
    if len(valid_files) > 5:
        errors.append("Cannot upload more than 5 images")
    else:
        for f in valid_files:
            name = f.filename
            ext = os.path.splitext(name.lower())[1]
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                errors.append(f"Image '{name}' must be JPG, PNG, or WebP")
                continue

            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)
            if size > 5 * 1024 * 1024:
                errors.append(f"Image '{name}' exceeds maximum size of 5 MB")
                continue
            if size == 0:
                errors.append(f"Image '{name}' is empty")
                continue

            ctype = getattr(f, "content_type", "")
            if ctype and ctype.lower() not in (
                "image/jpeg", "image/png", "image/webp", "application/octet-stream"
            ):
                errors.append(f"Image '{name}' has invalid MIME type '{ctype}'")
                continue

            header = f.read(16)
            f.seek(0)
            is_jpeg = header.startswith(b"\xff\xd8\xff")
            is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
            is_webp = (
                len(header) >= 12
                and header.startswith(b"RIFF")
                and header[8:12] == b"WEBP"
            )

            if ext in (".jpg", ".jpeg") and not is_jpeg:
                errors.append(f"Image '{name}' content does not match JPEG format")
            elif ext == ".png" and not is_png:
                errors.append(f"Image '{name}' content does not match PNG format")
            elif ext == ".webp" and not is_webp:
                errors.append(f"Image '{name}' content does not match WebP format")

    if errors:
        raise SearchError("VALIDATION_ERROR", "; ".join(errors), 422, errors=errors)

    return parsed_title, parsed_desc, parsed_cat_id, parsed_price, parsed_stock, valid_files


def create_product(user_id: int, data: dict, files=None) -> dict:
    """Create handcrafted product listing, images, and inventory record (OMH-F-005).

    Args:
        user_id (int): Authenticated user ID extracted from JWT token.
        data (dict): Request fields (title, desc/description, category_id, price, stock_qty).
        files (list): Uploaded image FileStorage objects (optional, max 5).

    Returns:
        dict: Created product summary with product_id.
    """
    title, desc, category_id, price, stock_qty, valid_files = validate_product_input(data, files)

    artisan = db.session.scalar(
        db.select(Artisan).where(Artisan.user_id == user_id)
    )
    if artisan is None:
        raise SearchError(
            "FORBIDDEN",
            "Artisan profile required to create listings",
            403,
        )

    upload_folder = get_upload_folder()
    saved_paths = []
    image_urls = []

    try:
        for f in valid_files:
            ext = os.path.splitext(f.filename.lower())[1]
            if ext == ".jpeg":
                ext = ".jpg"
            unique_name = f"{uuid.uuid4().hex}{ext}"
            dest_path = os.path.join(upload_folder, unique_name)
            f.seek(0)
            f.save(dest_path)
            saved_paths.append(dest_path)
            image_urls.append(f"/uploads/{unique_name}")

        product = Product(
            artisan_id=artisan.artisan_id,
            category_id=category_id,
            title=title,
            description=desc,
            price=price,
            is_active=True,
        )
        db.session.add(product)
        db.session.flush()

        for idx, url in enumerate(image_urls):
            img = ProductImage(
                product_id=product.product_id,
                image_url=url,
                is_primary=(idx == 0),
            )
            db.session.add(img)

        inv = Inventory(
            product_id=product.product_id,
            stock_quantity=stock_qty,
            low_stock_threshold=5,
        )
        db.session.add(inv)

        db.session.commit()
    except Exception:
        db.session.rollback()
        for p in saved_paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise

    return {
        "product_id": product.product_id,
        "title": product.title,
        "price": float(product.price),
        "stock_quantity": inv.stock_quantity,
        "category_id": product.category_id,
        "artisan_id": product.artisan_id,
        "is_active": product.is_active,
        "message": "Product listing created successfully",
    }


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
