from datetime import datetime, timezone

from flask import Blueprint, jsonify, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.invoices import service
from app.invoices.service import InvoiceError

bp = Blueprint("invoices", __name__, url_prefix="/api")


@bp.errorhandler(InvoiceError)
def handle_invoice_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


@bp.get("/orders/<int:order_id>/invoice")
@jwt_required()
def download_invoice(order_id):
    path, filename = service.get_invoice_file(
        order_id, int(get_jwt_identity()), get_jwt().get("role"))
    return send_file(path, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)
