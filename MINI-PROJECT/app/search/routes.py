from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.search import service
from app.search.service import SearchError

bp = Blueprint("search", __name__, url_prefix="/api")


@bp.errorhandler(SearchError)
def handle_search_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


def _int_arg(name, default=None):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise SearchError(
            "INVALID_INPUT", f"'{name}' must be a whole number", 422) from None


@bp.get("/products")
def list_products():
    q = request.args.get("q", "").strip()[:100]
    result = service.search_catalog(
        q=q or None,
        category_id=_int_arg("category"),
        page=_int_arg("page", 1),
        per_page=_int_arg("per_page", service.DEFAULT_PER_PAGE),
    )
    return jsonify(result)


@bp.get("/products/<int:product_id>")
def product_detail(product_id):
    return jsonify(service.get_product(product_id))


@bp.get("/categories")
def categories():
    return jsonify({"categories": service.list_categories()})
