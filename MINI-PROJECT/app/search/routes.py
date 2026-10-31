from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_from_directory
from flask_jwt_extended import get_jwt_identity

from app.middleware.rbac import role_required
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
    if getattr(e, "errors", None):
        body["errors"] = e.errors
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


@bp.post("/products")
@role_required("artisan")
def create_product():
    user_id = int(get_jwt_identity())
    if request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            raise SearchError("INVALID_INPUT", "Request body must be valid JSON", 400)
        files = []
    elif request.form or request.files:
        data = request.form.to_dict()
        files = request.files.getlist("images")
        if not files and "image" in request.files:
            files = request.files.getlist("image")
    else:
        data = request.get_json(silent=True)
        if data is not None:
            files = []
        else:
            data = request.form.to_dict()
            files = request.files.getlist("images")
            if not files and "image" in request.files:
                files = request.files.getlist("image")
            if not data and not files:
                raise SearchError("INVALID_INPUT", "Request body must not be empty", 400)

    result = service.create_product(user_id=user_id, data=data, files=files)
    return jsonify(result), 201


@bp.put("/products/<int:product_id>")
@role_required("artisan")
def update_product(product_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if data is None:
        raise SearchError("INVALID_INPUT", "Request body must be valid JSON", 400)
    result = service.update_product(user_id=user_id, product_id=product_id, data=data)
    return jsonify(result), 200


@bp.delete("/products/<int:product_id>")
@role_required("artisan")
def delete_product(product_id):
    user_id = int(get_jwt_identity())
    result = service.soft_delete_product(user_id=user_id, product_id=product_id)
    return jsonify(result), 200


@bp.get("/uploads/<path:filename>")
def get_upload(filename):
    return send_from_directory(service.get_upload_folder(), filename)


@bp.record_once
def _register_root_uploads(state):
    app = state.app
    if "root_uploads" not in app.view_functions:
        @app.get("/uploads/<path:filename>", endpoint="root_uploads")
        def root_upload(filename):
            return send_from_directory(service.get_upload_folder(), filename)
