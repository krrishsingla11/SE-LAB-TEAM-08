"""Report routes (OMH-F-019 / SE8-36)."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.middleware.rbac import role_required
from app.models import Artisan
from app.reports import service
from app.reports.service import ReportError

bp = Blueprint("reports", __name__, url_prefix="/api")


@bp.errorhandler(ReportError)
def handle_report_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


@bp.get("/reports/sales")
@role_required("artisan")
def sales_report():
    user_id = int(get_jwt_identity())
    artisan = db.session.scalars(
        db.select(Artisan).where(Artisan.user_id == user_id)
    ).first()
    if not artisan:
        raise ReportError("FORBIDDEN", "Artisan profile required", 403)

    period = request.args.get("period")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    month = request.args.get("month")
    year = request.args.get("year")

    limit = 10
    limit_raw = request.args.get("limit")
    if limit_raw is not None and limit_raw != "":
        try:
            limit = int(limit_raw)
            if limit <= 0 or limit > 100:
                raise ValueError()
        except ValueError:
            raise ReportError(
                "INVALID_INPUT",
                "'limit' must be a positive integer between 1 and 100.",
                400,
            ) from None

    analytics = service.aggregate_artisan_sales(
        artisan_id=artisan.artisan_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        month=month,
        year=year,
        limit=limit,
    )
    return jsonify(analytics), 200
