import logging
import os
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.invoices.generator import build_invoice_pdf
from app.models import Artisan, Invoice, Order, OrderItem, Product, User

log = logging.getLogger(__name__)


class InvoiceError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def invoice_dir():
    path = os.getenv("INVOICE_DIR") or os.path.join(os.getcwd(), "invoices")
    os.makedirs(path, exist_ok=True)
    return path


def _lines(order_id):
    rows = db.session.execute(
        db.select(OrderItem, Product.title)
        .join(Product, Product.product_id == OrderItem.product_id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.product_id)
    ).all()
    return [
        {
            "title": title,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "line_total": round(float(item.unit_price) * item.quantity, 2),
        }
        for item, title in rows
    ]


def _existing(order_id):
    return db.session.scalar(
        db.select(Invoice).where(Invoice.order_id == order_id))


def create_invoice(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        raise InvoiceError("NOT_FOUND", "Order not found", 404)
    invoice = _existing(order_id)
    now = datetime.now(timezone.utc)
    number = invoice.invoice_number if invoice else (
        f"INV-{now.year}-{order_id:06d}")
    full_path = os.path.join(invoice_dir(), f"{number}.pdf")
    if invoice is not None and os.path.exists(full_path):
        return invoice
    buyer = db.session.get(User, order.buyer_id)
    build_invoice_pdf(
        full_path, number, (invoice.issued_at if invoice else None) or now,
        order_id, getattr(buyer, "full_name", ""),
        getattr(buyer, "email", ""), order.shipping_address,
        _lines(order_id), round(float(order.total_amount), 2))
    if invoice is None:
        invoice = Invoice(order_id=order_id, invoice_number=number,
                          file_path=f"{number}.pdf", issued_at=now)
        db.session.add(invoice)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            invoice = _existing(order_id)
    return invoice


def _allowed(order, user_id, role):
    if role == "buyer":
        return order.buyer_id == user_id
    if role == "artisan":
        found = db.session.scalar(
            db.select(OrderItem.order_id)
            .join(Product, Product.product_id == OrderItem.product_id)
            .join(Artisan, Artisan.artisan_id == Product.artisan_id)
            .where(OrderItem.order_id == order.order_id,
                   Artisan.user_id == user_id)
            .limit(1))
        return found is not None
    return False


def get_invoice_file(order_id, user_id, role):
    order = db.session.get(Order, order_id)
    if order is None:
        raise InvoiceError("NOT_FOUND", "Order not found", 404)
    if not _allowed(order, user_id, role):
        raise InvoiceError(
            "FORBIDDEN", "Not authorized to access this invoice", 403)
    invoice = create_invoice(order_id)
    filename = f"{invoice.invoice_number}.pdf"
    return os.path.join(invoice_dir(), filename), filename
