"""ReportService (DS-RPT-01 / OMH-F-019 / SE8-36).

Provides artisan sales analytics and reporting aggregation over configurable
time periods and date ranges.
"""
import calendar
from datetime import datetime, time, timedelta, timezone
import logging
import re

from sqlalchemy import func

from app.extensions import db
from app.models import Order, OrderItem, Payment, Product

log = logging.getLogger(__name__)


class ReportError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _parse_iso_date(date_str, is_end=False):
    """Parse an ISO date/datetime string into a timezone-aware UTC datetime."""
    clean_str = date_str.strip().replace("Z", "+00:00")
    try:
        # Check if date-only format: YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", clean_str):
            dt = datetime.fromisoformat(clean_str)
            if is_end:
                dt = datetime.combine(dt.date(), time.max)
            else:
                dt = datetime.combine(dt.date(), time.min)
            return dt.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        field = "end_date" if is_end else "start_date"
        raise ReportError(
            "INVALID_DATE_FORMAT",
            f"Invalid {field} format. Use ISO format (YYYY-MM-DD).",
            400,
        ) from None


def _resolve_period_bounds(
    period=None,
    start_date_str=None,
    end_date_str=None,
    month_param=None,
    year_param=None,
):
    """Determine the [start_date, end_date] range and resolved period label."""
    now = datetime.now(timezone.utc)

    # 1. Explicit start_date or end_date
    if start_date_str or end_date_str:
        start_dt = (
            _parse_iso_date(start_date_str, is_end=False)
            if start_date_str
            else None
        )
        end_dt = (
            _parse_iso_date(end_date_str, is_end=True)
            if end_date_str
            else None
        )
        if start_dt and end_dt and start_dt > end_dt:
            raise ReportError(
                "INVALID_DATE_RANGE",
                "start_date cannot be after end_date.",
                400,
            )
        return start_dt, end_dt, "custom"

    # 2. Month query parameter (e.g. month=2026-10 or month=10&year=2026)
    if month_param:
        clean_month = str(month_param).strip()
        if re.match(r"^\d{4}-\d{2}$", clean_month):
            y, m = int(clean_month[:4]), int(clean_month[5:7])
        else:
            try:
                m = int(clean_month)
                y = int(year_param) if year_param else now.year
            except ValueError:
                raise ReportError(
                    "INVALID_PERIOD", "Invalid month parameter.", 400
                ) from None
        if not (1 <= m <= 12):
            raise ReportError(
                "INVALID_PERIOD", "Month must be between 1 and 12.", 400
            )
        _, last_day = calendar.monthrange(y, m)
        start_dt = datetime(y, m, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(
            y, m, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc
        )
        return start_dt, end_dt, f"{y:04d}-{m:02d}"

    # 3. Standard period string
    p = (period or "monthly").strip().lower()

    if p in ("monthly", "month"):
        _, last_day = calendar.monthrange(now.year, now.month)
        start_dt = datetime(
            now.year, now.month, 1, 0, 0, 0, 0, tzinfo=timezone.utc
        )
        end_dt = datetime(
            now.year, now.month, last_day, 23, 59, 59, 999999,
            tzinfo=timezone.utc,
        )
        return start_dt, end_dt, "monthly"

    if p in ("weekly", "week", "7d"):
        monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sunday = (monday + timedelta(days=6)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        return monday, sunday, "weekly"

    if p in ("30d", "last30days"):
        start_dt = (now - timedelta(days=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_dt, end_dt, "30d"

    if p in ("yearly", "year"):
        start_dt = datetime(now.year, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(
            now.year, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc
        )
        return start_dt, end_dt, "yearly"

    if p in ("all", "all-time", "all_time"):
        return None, None, "all"

    if re.match(r"^\d{4}-\d{2}$", p):
        y, m = int(p[:4]), int(p[5:7])
        if not (1 <= m <= 12):
            raise ReportError(
                "INVALID_PERIOD", f"Invalid month in period: '{p}'.", 400
            )
        _, last_day = calendar.monthrange(y, m)
        start_dt = datetime(y, m, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(
            y, m, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc
        )
        return start_dt, end_dt, p

    raise ReportError(
        "INVALID_PERIOD",
        f"Unsupported period '{period}'. "
        "Allowed: monthly, weekly, yearly, all, or YYYY-MM.",
        400,
    )


def aggregate_artisan_sales(
    artisan_id,
    period=None,
    start_date=None,
    end_date=None,
    month=None,
    year=None,
    limit=10,
):
    """Aggregate gross revenue, units sold, order count, and top craft items.

    Conforms to IReportContract / OMH-F-019.
    """
    start_dt, end_dt, resolved_period = _resolve_period_bounds(
        period=period,
        start_date_str=start_date,
        end_date_str=end_date,
        month_param=month,
        year_param=year,
    )

    # Base completed order conditions:
    # 1. Product belongs to this artisan
    # 2. Order status is in ('Processing', 'Shipped', 'Delivered')
    # 3. Payment record exists and status is strictly 'captured'
    conditions = [
        Product.artisan_id == artisan_id,
        Order.status.in_(["Processing", "Shipped", "Delivered"]),
        Payment.payment_status == "captured",
    ]

    if start_dt is not None:
        conditions.append(Order.created_at >= start_dt)
    if end_dt is not None:
        conditions.append(Order.created_at <= end_dt)

    # 1. Single summary aggregation query
    summary_stmt = (
        db.select(
            func.coalesce(
                func.sum(OrderItem.quantity * OrderItem.unit_price), 0
            ).label("revenue"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.count(func.distinct(Order.order_id)).label("order_count"),
        )
        .select_from(OrderItem)
        .join(Product, Product.product_id == OrderItem.product_id)
        .join(Order, Order.order_id == OrderItem.order_id)
        .join(Payment, Payment.order_id == Order.order_id)
        .where(*conditions)
    )

    summary_row = db.session.execute(summary_stmt).one()
    revenue_val = round(float(summary_row.revenue), 2)
    units_sold_val = int(summary_row.units_sold)
    order_count_val = int(summary_row.order_count)

    # 2. Top-selling craft items aggregation query
    top_items = []
    if order_count_val > 0:
        top_stmt = (
            db.select(
                Product.product_id,
                Product.title,
                func.sum(OrderItem.quantity).label("item_units"),
                func.sum(
                    OrderItem.quantity * OrderItem.unit_price
                ).label("item_revenue"),
            )
            .select_from(OrderItem)
            .join(Product, Product.product_id == OrderItem.product_id)
            .join(Order, Order.order_id == OrderItem.order_id)
            .join(Payment, Payment.order_id == Order.order_id)
            .where(*conditions)
            .group_by(Product.product_id, Product.title)
            .order_by(
                func.sum(OrderItem.quantity).desc(),
                func.sum(OrderItem.quantity * OrderItem.unit_price).desc(),
            )
            .limit(limit)
        )
        top_rows = db.session.execute(top_stmt).all()
        top_items = [
            {
                "product_id": r.product_id,
                "title": r.title,
                "units_sold": int(r.item_units),
                "units": int(r.item_units),
                "revenue": round(float(r.item_revenue), 2),
            }
            for r in top_rows
        ]

    return {
        "revenue": revenue_val,
        "gross_revenue": revenue_val,
        "order_count": order_count_val,
        "units_sold": units_sold_val,
        "units": units_sold_val,
        "top_items": top_items,
        "period": resolved_period,
        "start_date": start_dt.isoformat() if start_dt else None,
        "end_date": end_dt.isoformat() if end_dt else None,
    }
