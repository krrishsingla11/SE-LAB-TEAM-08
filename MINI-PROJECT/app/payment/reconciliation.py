from decimal import Decimal
import logging
import uuid

from app.extensions import db
from app.models import Payment, PaymentAttempt
from app.payment.gateway import (
    MockGateway,
    PaymentError,
    RazorpayGateway,
    paise_to_rupees,
    rupees_to_paise,
)
from app.payment.service import get_gateway

logger = logging.getLogger(__name__)


def reconcile_payment_attempt(attempt_id: int, buyer_id: int = None) -> dict:
    """Reconcile a single PaymentAttempt against gateway state and database records.

    Distinguishes:
    - Already fulfilled marketplace order (never refunded)
    - No payment ID or uncaptured payment
    - Verification failed (inconsistent details)
    - No refund
    - Pending refund
    - Processed full refund
    - Failed refund
    - Partial refund (unexpected partial refund never marked fully refunded)
    """
    attempt = db.session.scalar(
        db.select(PaymentAttempt)
        .where(PaymentAttempt.attempt_id == attempt_id)
        .with_for_update()
    )
    if attempt is None:
        raise ValueError(f"PaymentAttempt {attempt_id} not found")

    # Enforce buyer ownership when buyer_id is provided
    if buyer_id is not None and attempt.buyer_id != buyer_id:
        raise PermissionError("Unauthorized: cannot reconcile another buyer's payment attempt")

    # 1. Inspect whether this payment fulfilled a marketplace order
    if attempt.razorpay_payment_id:
        existing_payment = db.session.scalar(
            db.select(Payment).where(
                Payment.transaction_ref == attempt.razorpay_payment_id
            )
        )
        if existing_payment is not None:
            # FULFILLED MARKETPLACE ORDER: Never refund
            if attempt.status != "completed":
                attempt.status = "completed"
                db.session.commit()
            return {
                "status": "already_fulfilled_order",
                "attempt_id": attempt.attempt_id,
                "order_id": existing_payment.order_id,
                "payment_id": existing_payment.payment_id,
            }

    if not attempt.razorpay_payment_id:
        return {
            "status": "no_payment_id",
            "attempt_id": attempt.attempt_id,
        }

    gateway = get_gateway()
    if isinstance(gateway, RazorpayGateway):
        try:
            agg = gateway.fetch_payment(attempt.razorpay_payment_id)
            refunds_data = gateway.fetch_multiple_refund(attempt.razorpay_payment_id)
        except PaymentError as err:
            logger.warning(
                "Reconciliation gateway fetch error for attempt %s: %s",
                attempt.attempt_id,
                err.message,
            )
            return {
                "status": "gateway_error",
                "attempt_id": attempt.attempt_id,
                "error": "Payment gateway communication failed",
            }
    elif isinstance(gateway, MockGateway):
        # Deterministic mock gateway handling
        agg = {
            "id": attempt.razorpay_payment_id,
            "order_id": attempt.razorpay_order_id,
            "amount": rupees_to_paise(attempt.amount),
            "amount_refunded": (
                rupees_to_paise(attempt.amount) if attempt.status == "refunded" else 0
            ),
            "refund_status": "full" if attempt.status == "refunded" else None,
            "currency": "INR",
            "status": "captured",
        }
        refunds_data = {
            "count": 1 if attempt.status == "refunded" else 0,
            "items": [
                {
                    "id": attempt.refund_ref or "rfnd_mock_1",
                    "payment_id": attempt.razorpay_payment_id,
                    "amount": rupees_to_paise(attempt.amount),
                    "status": "processed",
                }
            ] if attempt.status == "refunded" else [],
        }
    else:
        return {
            "status": "unsupported_gateway",
            "attempt_id": attempt.attempt_id,
        }

    expected_paise = rupees_to_paise(attempt.amount)

    # 2. Strict validation of fetched payment against PaymentAttempt before refund
    fetched_pid = str(agg.get("id") or "").strip()
    fetched_oid = str(agg.get("order_id") or "").strip()
    fetched_curr = str(agg.get("currency") or "").strip().upper()
    fetched_status = str(agg.get("status") or "").strip().lower()
    try:
        fetched_amt = int(agg.get("amount", 0))
    except (ValueError, TypeError):
        fetched_amt = 0

    if (
        fetched_pid != attempt.razorpay_payment_id.strip()
        or fetched_oid != attempt.razorpay_order_id.strip()
        or fetched_amt != expected_paise
        or fetched_curr != "INR"
        or fetched_status != "captured"
    ):
        logger.error(
            "Reconciliation mismatch for attempt %s: pid=%s/%s, oid=%s/%s",
            attempt.attempt_id,
            fetched_pid, attempt.razorpay_payment_id,
            fetched_oid, attempt.razorpay_order_id,
        )
        attempt.status = "manual_review"
        attempt.failure_reason = "payment verification mismatch during reconciliation"
        db.session.commit()
        return {
            "status": "verification_failed",
            "attempt_id": attempt.attempt_id,
        }

    raw_items = refunds_data.get("items", []) if isinstance(refunds_data, dict) else []
    # Account for all refund entities belonging to this payment
    refund_items = [
        r for r in raw_items
        if str(r.get("payment_id", "") or "").strip() == attempt.razorpay_payment_id.strip()
        or not r.get("payment_id")  # SDK sometimes omits payment_id in nested items
    ]

    # Calculate total processed refunds from valid items and aggregate
    processed_items = [r for r in refund_items if str(r.get("status") or "").lower() == "processed"]
    processed_sum = sum(int(r.get("amount", 0)) for r in processed_items)
    agg_refunded = int(agg.get("amount_refunded") or 0)
    total_refunded = max(processed_sum, agg_refunded)

    # Check for pending refunds
    has_pending = any(str(r.get("status") or "").lower() == "pending" for r in refund_items)

    if has_pending:
        attempt.status = "refund_pending"
        db.session.commit()
        return {
            "status": "pending_refund",
            "attempt_id": attempt.attempt_id,
        }

    # Full refund verified
    if total_refunded == expected_paise:
        attempt.status = "refunded"
        attempt.unrefunded_amount = Decimal("0.00")
        if processed_items:
            attempt.refund_ref = processed_items[0].get("id")
        db.session.commit()
        return {
            "status": "processed_full_refund",
            "attempt_id": attempt.attempt_id,
            "refund_id": attempt.refund_ref,
        }

    # Partial refund verified: NEVER mark fully refunded
    if 0 < total_refunded < expected_paise:
        attempt.status = "partial_refunded"
        unrefunded_paise = expected_paise - total_refunded
        attempt.unrefunded_amount = paise_to_rupees(unrefunded_paise)
        if processed_items:
            attempt.refund_ref = processed_items[0].get("id")
        db.session.commit()
        return {
            "status": "partial_refund",
            "attempt_id": attempt.attempt_id,
            "unrefunded_amount": float(attempt.unrefunded_amount),
        }

    # Case A: If refund items exist and all are confirmed failed at the gateway:
    # A confirmed terminal failure must be recorded accurately.
    # Repeated observation of the same terminal failed refund must not increment retry_count.
    # If another automatic attempt is permitted (< 3), it must be a genuinely
    # new refund request with a newly persisted idempotency key, created only after
    # the previous refund is confirmed failed.
    all_failed = bool(refund_items) and all(
        str(r.get("status") or "").lower() == "failed" for r in refund_items
    )
    if all_failed and total_refunded == 0:
        failed_ref_id = refund_items[0].get("id") if refund_items else attempt.refund_ref

        # Stop at configured retry limit (>= 3) or if already escalated to manual_review
        if attempt.retry_count >= 3 or attempt.status == "manual_review":
            attempt.status = "manual_review"
            if failed_ref_id:
                attempt.refund_ref = failed_ref_id
            db.session.commit()
            return {
                "status": "failed_refund",
                "attempt_id": attempt.attempt_id,
            }

        # Eligible for a genuinely new retry (< 3)
        # Preserve durable audit history of previous refund attempt and key in failure_reason
        old_key = attempt.refund_idempotency_key
        audit_entry = (
            f"[retry {attempt.retry_count + 1}] "
            f"prev_failed_ref={failed_ref_id}, prev_key={old_key}"
        )
        attempt.failure_reason = (
            f"{attempt.failure_reason}; {audit_entry}"
            if attempt.failure_reason
            else audit_entry
        )

        # Generate a genuinely new idempotency key for this new dispatch attempt
        new_idempotency_key = f"rfk_{uuid.uuid4().hex}"
        attempt.refund_idempotency_key = new_idempotency_key
        attempt.retry_count += 1
        attempt.status = "refund_pending"
        db.session.commit()

        try:
            res = gateway.void_or_refund_charge(
                attempt.razorpay_payment_id,
                reason=attempt.failure_reason or f"reconciliation retry {attempt.retry_count}",
                amount=attempt.amount,
                idempotency_key=attempt.refund_idempotency_key,
            )
            attempt.refund_ref = res.get("refund_id")
            p_status = res.get("payment_status")
            actual_paise = res.get("amount_refunded")

            if p_status == "refunded":
                attempt.status = "refunded"
                attempt.unrefunded_amount = Decimal("0.00")
            elif p_status == "partial_refunded" or (
                actual_paise is not None and actual_paise < expected_paise
            ):
                attempt.status = "partial_refunded"
                unrefunded_paise = expected_paise - (actual_paise or 0)
                attempt.unrefunded_amount = paise_to_rupees(unrefunded_paise)
            elif p_status == "refund_pending":
                attempt.status = "refund_pending"
            elif p_status == "refund_failed":
                if attempt.retry_count >= 3:
                    attempt.status = "manual_review"
                else:
                    attempt.status = "refund_failed"
            else:
                attempt.status = "manual_review"
            db.session.commit()
            return {
                "status": "refund_dispatched",
                "attempt_id": attempt.attempt_id,
                "refund_id": attempt.refund_ref,
            }
        except Exception as err:
            logger.warning(
                "Refund dispatch failure in reconciliation for attempt %s: %s",
                attempt.attempt_id,
                type(err).__name__,
            )
            if attempt.retry_count >= 3:
                attempt.status = "manual_review"
            else:
                attempt.status = "refund_failed"
            db.session.commit()
            return {
                "status": "failed_refund",
                "attempt_id": attempt.attempt_id,
            }

    # Case B: If NO refund items exist at all at gateway (ambiguous network timeout recovery)
    if not refund_items and total_refunded == 0:
        # Check if attempt is eligible for retry (< 3)
        if attempt.status in ("refund_pending", "refund_failed") and attempt.retry_count < 3:
            # Reusing the exact same persisted idempotency key and payload (idempotency stability)
            if not attempt.refund_idempotency_key:
                attempt.refund_idempotency_key = f"rfk_{uuid.uuid4().hex}"
                db.session.commit()

            # Increment retry_count on actual dispatch
            attempt.retry_count += 1
            try:
                res = gateway.void_or_refund_charge(
                    attempt.razorpay_payment_id,
                    reason=attempt.failure_reason or "reconciliation retry",
                    amount=attempt.amount,
                    idempotency_key=attempt.refund_idempotency_key,
                )
                attempt.refund_ref = res.get("refund_id")
                p_status = res.get("payment_status")
                actual_paise = res.get("amount_refunded")

                if p_status == "refunded":
                    attempt.status = "refunded"
                    attempt.unrefunded_amount = Decimal("0.00")
                elif p_status == "partial_refunded" or (
                    actual_paise is not None and actual_paise < expected_paise
                ):
                    attempt.status = "partial_refunded"
                    unrefunded_paise = expected_paise - (actual_paise or 0)
                    attempt.unrefunded_amount = paise_to_rupees(unrefunded_paise)
                elif p_status == "refund_pending":
                    attempt.status = "refund_pending"
                elif p_status == "refund_failed":
                    if attempt.retry_count >= 3:
                        attempt.status = "manual_review"
                    else:
                        attempt.status = "refund_failed"
                else:
                    attempt.status = "manual_review"
                db.session.commit()
                return {
                    "status": "refund_dispatched",
                    "attempt_id": attempt.attempt_id,
                    "refund_id": attempt.refund_ref,
                }
            except Exception as err:
                logger.warning(
                    "Refund dispatch failure in reconciliation for attempt %s: %s",
                    attempt.attempt_id,
                    type(err).__name__,
                )
                if attempt.retry_count >= 3:
                    attempt.status = "manual_review"
                else:
                    attempt.status = "refund_failed"
                db.session.commit()
                return {
                    "status": "failed_refund",
                    "attempt_id": attempt.attempt_id,
                }
                return {
                    "status": "failed_refund",
                    "attempt_id": attempt.attempt_id,
                    "error": "Payment gateway communication failed",
                }

        # Terminal state already reached: do not increment retry count again!
        if attempt.retry_count >= 3 or attempt.status == "manual_review":
            attempt.status = "manual_review"
            db.session.commit()
            return {
                "status": "manual_review",
                "attempt_id": attempt.attempt_id,
            }

        return {
            "status": "no_refund",
            "attempt_id": attempt.attempt_id,
        }

    return {
        "status": attempt.status,
        "attempt_id": attempt.attempt_id,
    }


def reconcile_all_pending(limit: int = 50) -> list:
    """Reconcile pending or failed payment attempts up to the specified limit."""
    attempts = db.session.scalars(
        db.select(PaymentAttempt)
        .where(PaymentAttempt.status.in_(["refund_pending", "refund_failed"]))
        .order_by(PaymentAttempt.updated_at.asc())
        .limit(limit)
    ).all()
    results = []
    for att in attempts:
        results.append(reconcile_payment_attempt(att.attempt_id))
    return results
