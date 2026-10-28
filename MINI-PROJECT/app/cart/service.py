from app.extensions import db
from app.models import Cart, CartItem, Product, Inventory


class CartError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _cart(buyer_id):
    cart = db.session.scalar(db.select(Cart).where(Cart.buyer_id == buyer_id))
    if cart is None:
        cart = Cart(buyer_id=buyer_id)
        db.session.add(cart)
        db.session.flush()
    return cart


def _stock(product_id):
    inv = db.session.scalar(
        db.select(Inventory).where(Inventory.product_id == product_id))
    return inv.stock_quantity if inv else 0


def _valid_qty(qty):
    if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
        raise CartError(
            "INVALID_QUANTITY",
            "Quantity must be a whole number of at least 1", 422)


def _check(product_id, qty):
    _valid_qty(qty)
    product = db.session.get(Product, product_id)
    if product is None or not product.is_active:
        raise CartError("NOT_FOUND", "Product not found", 404)
    stock = _stock(product_id)
    if qty > stock:
        raise CartError(
            "INSUFFICIENT_STOCK",
            f"Requested quantity exceeds available inventory ({stock})")
    return product


def _item(cart, product_id):
    return db.session.scalar(db.select(CartItem).where(
        CartItem.cart_id == cart.cart_id,
        CartItem.product_id == product_id))


def get_cart(buyer_id):
    cart = _cart(buyer_id)
    lines = []
    subtotal = 0.0
    items = db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id))
    for item in items:
        product = db.session.get(Product, item.product_id)
        item.unit_price = product.price  # always use the current price
        total = float(item.unit_price) * item.quantity
        subtotal += total
        lines.append({
            "product_id": item.product_id,
            "title": product.title,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "line_total": round(total, 2),
        })
    db.session.commit()
    return {"cart": lines, "subtotal": round(subtotal, 2)}


def add_item(buyer_id, product_id, qty):
    _valid_qty(qty)
    cart = _cart(buyer_id)
    item = _item(cart, product_id)
    new_qty = qty + (item.quantity if item else 0)
    product = _check(product_id, new_qty)
    if item:
        item.quantity = new_qty
    else:
        db.session.add(CartItem(
            cart_id=cart.cart_id, product_id=product_id,
            quantity=qty, unit_price=product.price))
    db.session.commit()
    return get_cart(buyer_id)


def update_qty(buyer_id, product_id, qty):
    cart = _cart(buyer_id)
    item = _item(cart, product_id)
    if item is None:
        raise CartError("NOT_FOUND", "Item not in cart", 404)
    _check(product_id, qty)
    item.quantity = qty
    db.session.commit()
    return get_cart(buyer_id)


def remove_item(buyer_id, product_id):
    cart = _cart(buyer_id)
    item = _item(cart, product_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return get_cart(buyer_id)


def clear_cart(buyer_id):
    cart = _cart(buyer_id)
    items = db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id))
    for item in items:
        db.session.delete(item)
    db.session.commit()
