from decimal import Decimal
import json
import logging
import re
import uuid

from app.checkout.stock import (
    OutOfStock,
    decrement_stock,
    lock_and_validate_stock,
)
from app.extensions import db
from app.invoices import service as invoice_service
from app.models import Cart, CartItem, Order, OrderItem, Payment, PaymentAttempt, Product
from app.payment import service as payment_service
from app.payment.gateway import CARD_NUMBER, PaymentError, paise_to_rupees, rupees_to_paise
from app.payment.routes import compute_cart_hash

log = logging.getLogger(__name__)

MAX_ADDRESS_LENGTH = 500


class OrderError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _clean_address(address):
    if not isinstance(address, str) or not address.strip():
        raise OrderError("INVALID_ADDRESS", "shipping_address is required", 422)
    if len(address.strip()) > MAX_ADDRESS_LENGTH:
        raise OrderError("INVALID_ADDRESS", "shipping_address is too long", 422)
    return address.strip()


def _cart_lines(buyer_id, for_update=False):
    stmt = db.select(Cart).where(Cart.buyer_id == buyer_id)
    if for_update:
        stmt = stmt.with_for_update()
    cart = db.session.scalar(stmt)
    if cart is None:
        return []
    items_stmt = db.select(CartItem).where(CartItem.cart_id == cart.cart_id)
    if for_update:
        items_stmt = items_stmt.with_for_update()
    return db.session.scalars(items_stmt).all()


def _current_prices(lines):
    # Prices always come from the database, never from the client.
    prices = {}
    for line in lines:
        product = db.session.get(Product, line.product_id)
        if product is None or not product.is_active:
            raise OrderError(
                "PRODUCT_UNAVAILABLE",
                "A product in your cart is no longer available",
                400,
            )
        prices[line.product_id] = round(float(product.price), 2)
    return prices


def _refund(charge, reason, amount=None, idempotency_key=None):
    if charge is not None:
        payment_service.void_or_refund_charge(
            charge["transaction_ref"],
            reason=reason,
            amount=amount,
            idempotency_key=idempotency_key,
        )
        log.error("Charge %s refunded: %s", charge["transaction_ref"], reason)


def _save_order(buyer_id, address, lines, prices, total, charge):
    order = Order(
        buyer_id=buyer_id,
        total_amount=total,
        status="Processing",
        shipping_address=address,
    )
    db.session.add(order)
    db.session.flush()
    for line in lines:
        db.session.add(
            OrderItem(
                order_id=order.order_id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=prices[line.product_id],
            )
        )
        db.session.delete(line)
    db.session.add(
        Payment(
            order_id=order.order_id,
            transaction_ref=charge["transaction_ref"],
            amount=total,
            payment_status="captured",
        )
    )
    return order


def _summary(order, charge):
    return {
        "order_id": order.order_id,
        "status": order.status,
        "payment_status": "captured",
        "total": float(order.total_amount),
        "transaction_ref": charge["transaction_ref"],
        "invoice_url": f"/api/orders/{order.order_id}/invoice",
    }


def _parse_payment_input(payment_token, razorpay_order_id,
                         razorpay_payment_id, razorpay_signature):
    """Normalize payment credentials into Razorpay triplet or mock token."""
    order_id = razorpay_order_id
    payment_id = razorpay_payment_id
    signature = razorpay_signature

    if isinstance(payment_token, dict):
        order_id = order_id or payment_token.get("razorpay_order_id")
        payment_id = payment_id or payment_token.get("razorpay_payment_id")
        signature = signature or payment_token.get("razorpay_signature")
    elif isinstance(payment_token, str):
        clean_token = payment_token.strip()
        if clean_token.startswith("{") and clean_token.endswith("}"):
            try:
                data = json.loads(clean_token)
                order_id = order_id or data.get("razorpay_order_id")
                payment_id = payment_id or data.get("razorpay_payment_id")
                signature = signature or data.get("razorpay_signature")
            except Exception:
                raise OrderError("INVALID_TOKEN", "Malformed JSON payment token", 422)
        elif "|" in clean_token:
            parts = clean_token.split("|")
            if len(parts) == 3:
                order_id = order_id or parts[0].strip()
                payment_id = payment_id or parts[1].strip()
                signature = signature or parts[2].strip()
            else:
                raise OrderError("INVALID_TOKEN", "Malformed pipe-delimited payment token", 422)
        elif clean_token.startswith("tok_"):
            return "mock", clean_token, None, None, None

    if order_id or payment_id or signature:
        if not (order_id and payment_id and signature):
            raise OrderError(
                "INVALID_TOKEN",
                "razorpay_order_id, razorpay_payment_id, and razorpay_signature are required",
                422,
            )
        return (
            "razorpay", None, str(order_id).strip(),
            str(payment_id).strip(), str(signature).strip()
        )

    if isinstance(payment_token, str) and payment_token.strip():
        clean_token = payment_token.strip()
        if CARD_NUMBER.match(re.sub(r"[\s-]", "", clean_token)):
            raise OrderError(
                "RAW_CARD_DATA_REJECTED",
                "Send a payment token, never a card number",
                400,
            )
        return "mock", clean_token, None, None, None

    raise OrderError("INVALID_TOKEN", "A payment token is required", 422)


def _compensate_stock_cart_failure(attempt_id, order_id, payment_id, signature,
                                   error_code, error_message, reason):
    """Execute strictly fail-closed verification and compensating refund."""
    # 1. Rollback transaction immediately to release cart & inventory locks
    db.session.rollback()

    gateway = payment_service.get_gateway()

    # Fail-closed: gateway must implement callable verification methods
    if (
        not callable(getattr(gateway, "verify_payment_signature", None))
        or not callable(getattr(gateway, "verify_payment", None))
    ):
        log.error("Gateway verification capability missing; refund blocked for %s", payment_id)
        if attempt_id:
            try:
                att = db.session.get(PaymentAttempt, attempt_id)
                if att:
                    att.status = "manual_review"
                    att.failure_reason = "payment verification unavailable; refund blocked"
                    db.session.commit()
            except Exception:
                pass
        raise OrderError(
            "PAYMENT_VERIFICATION_UNAVAILABLE",
            "Payment verification unavailable; refund blocked for manual review",
            500,
        )

    # 2. Verify signature cryptographically before initiating any refund
    try:
        gateway.verify_payment_signature(order_id, payment_id, signature)
    except PaymentError as sig_err:
        log.warning("Invalid payment signature during abort for payment %s", payment_id)
        raise OrderError(
            "INVALID_SIGNATURE",
            "Payment signature verification failed; no refund issued",
            400,
        ) from sig_err

    # 3. Fetch payment and assert order binding, amount, currency, and captured status
    attempt = db.session.get(PaymentAttempt, attempt_id) if attempt_id else None
    if not attempt:
        raise OrderError("INVALID_ORDER", "Payment attempt not found; no refund issued", 400)

    try:
        payment_data = gateway.verify_payment(
            payment_id,
            expected_amount=attempt.amount,
            expected_currency="INR",
            expected_order_id=order_id,
        )
    except PaymentError as ver_err:
        log.warning(
            "Payment verification failed during abort for payment %s: %s",
            payment_id,
            ver_err.message,
        )
        raise OrderError(
            ver_err.code,
            f"Payment verification failed: {ver_err.message}; no refund issued",
            400,
        ) from ver_err

    # Strict check: fetched payment ID must match supplied payment ID
    fetched_id = str(payment_data.get("id") or "").strip()
    if fetched_id != str(payment_id).strip():
        log.error("Fetched payment ID mismatch: expected %s, got %s", payment_id, fetched_id)
        raise OrderError(
            "PAYMENT_ID_MISMATCH",
            "Fetched payment ID mismatch; no refund issued",
            400,
        )

    # 4. Open fresh transaction to record refund_pending and persist idempotency key
    fresh_attempt = db.session.scalar(
        db.select(PaymentAttempt)
        .where(PaymentAttempt.attempt_id == attempt_id)
        .with_for_update()
    )
    if fresh_attempt.status == "completed":
        raise OrderError("ALREADY_COMPLETED", "Payment attempt already fulfilled", 409)

    fresh_attempt.status = "refund_pending"
    fresh_attempt.failure_reason = reason
    fresh_attempt.razorpay_payment_id = payment_id
    if not fresh_attempt.refund_idempotency_key:
        fresh_attempt.refund_idempotency_key = f"rfk_{uuid.uuid4().hex}"
    db.session.commit()

    # 5. Dispatch compensating refund using persisted idempotency key
    try:
        res = payment_service.void_or_refund_charge(
            payment_id,
            reason=reason,
            amount=fresh_attempt.amount,
            idempotency_key=fresh_attempt.refund_idempotency_key,
        )
        fresh_attempt = db.session.get(PaymentAttempt, attempt_id)
        fresh_attempt.refund_ref = res.get("refund_id")
        p_status = res.get("payment_status")
        expected_paise = rupees_to_paise(fresh_attempt.amount)
        actual_paise = res.get("amount_refunded")

        if p_status == "refunded":
            fresh_attempt.status = "refunded"
            fresh_attempt.unrefunded_amount = Decimal("0.00")
        elif p_status == "partial_refunded" or (
            actual_paise is not None and actual_paise < expected_paise
        ):
            fresh_attempt.status = "partial_refunded"
            unrefunded_paise = expected_paise - (actual_paise or 0)
            fresh_attempt.unrefunded_amount = paise_to_rupees(unrefunded_paise)
        elif p_status == "refund_pending":
            fresh_attempt.status = "refund_pending"
        elif p_status == "refund_failed":
            fresh_attempt.retry_count += 1
            if fresh_attempt.retry_count >= 3:
                fresh_attempt.status = "manual_review"
            else:
                fresh_attempt.status = "refund_failed"
        else:
            fresh_attempt.status = "manual_review"
            fresh_attempt.failure_reason = f"inconsistent refund response: {res}"
        db.session.commit()
    except Exception as ref_err:
        log.exception(
            "Compensating refund dispatch failed for payment %s: %s",
            payment_id,
            ref_err,
        )
        fresh_attempt = db.session.get(PaymentAttempt, attempt_id)
        fresh_attempt.retry_count += 1
        fresh_attempt.failure_reason = f"refund dispatch error: {ref_err}"
        if fresh_attempt.retry_count >= 3:
            fresh_attempt.status = "manual_review"
        else:
            fresh_attempt.status = "refund_failed"
        db.session.commit()

    raise OrderError(error_code, error_message, 400)


def _handle_post_verification_failure(buyer_id, attempt, charge):
    """Safely handle failures during post-verification order creation, decrement, or commit."""
    # Step 1: Ensure failed checkout transaction is rolled back
    db.session.rollback()

    payment_id = charge.get("transaction_ref") if charge else None
    if not payment_id:
        raise OrderError(
            "ORDER_FAILED",
            "The order could not be completed. Please try again.",
            500,
        )

    attempt_id = attempt.attempt_id if attempt else None
    if not attempt_id:
        log.critical("PaymentAttempt record missing in recovery; flagged for manual review")
        raise OrderError(
            "ORDER_UNCERTAIN",
            "Missing payment attempt record; flagged for manual review",
            500,
        )

    # Step 2: In a fresh transaction, acquire row lock on PaymentAttempt with SELECT ... FOR UPDATE
    # and refresh state from the database to avoid stale identity-map data
    try:
        fresh_attempt = db.session.scalar(
            db.select(PaymentAttempt)
            .where(PaymentAttempt.attempt_id == attempt_id)
            .with_for_update()
        )
        if fresh_attempt is None:
            log.critical(
                "PaymentAttempt %s missing in recovery lock; flagged for manual review",
                attempt_id,
            )
            raise OrderError(
                "ORDER_UNCERTAIN",
                "Missing payment attempt record; flagged for manual review",
                500,
            )
        db.session.refresh(fresh_attempt)

        # While holding this lock, query Payment.transaction_ref again
        existing_payment = db.session.scalar(
            db.select(Payment).where(Payment.transaction_ref == payment_id)
        )
    except OrderError:
        raise
    except Exception as query_err:
        log.exception("Failed to query persistence in post-verification recovery: %s", query_err)
        try:
            db.session.rollback()
            att = db.session.get(PaymentAttempt, attempt_id)
            if att and att.status != "completed":
                att.status = "manual_review"
                att.failure_reason = f"post-verification query failed: {query_err}"
                db.session.commit()
        except Exception:
            pass
        raise OrderError(
            "ORDER_UNCERTAIN",
            "Order outcome uncertain; flagged for manual review",
            500,
        )

    # Step 3: If payment belongs to a persisted marketplace order or attempt is already completed:
    # Mark/reconcile attempt as completed and NEVER refund!
    if existing_payment is not None or fresh_attempt.status == "completed":
        log.info(
            "Post-verification failure recovered: Order/Payment persisted "
            "(attempt %s, payment %s).",
            attempt_id,
            payment_id,
        )
        if fresh_attempt.status != "completed":
            fresh_attempt.status = "completed"
            fresh_attempt.razorpay_payment_id = payment_id
            db.session.commit()
        if existing_payment:
            order = db.session.get(Order, existing_payment.order_id)
            if order:
                return _summary(order, charge)
        return {
            "order_id": getattr(existing_payment, "order_id", None),
            "status": "completed",
            "message": "Order fulfilled",
        }

    # Step 4: If database definitively confirms no Order/Payment persisted and attempt is safely
    # eligible for compensation:
    # Commit refund-pending state and idempotency key BEFORE making the refund HTTP request
    if (
        existing_payment is None
        and fresh_attempt.status not in ("completed", "paid", "refunded")
    ):
        log.warning(
            "Post-verification failure confirmed not persisted for attempt %s. "
            "Initiating compensation.",
            attempt_id,
        )
        fresh_attempt.status = "refund_pending"
        fresh_attempt.failure_reason = "post-verification database failure"
        fresh_attempt.razorpay_payment_id = payment_id
        if not fresh_attempt.refund_idempotency_key:
            fresh_attempt.refund_idempotency_key = f"rfk_{uuid.uuid4().hex}"

        # Commit durable state to DB before dispatching HTTP refund
        db.session.commit()

        # Step 5: Perform the refund HTTP request only after this durable state is committed
        try:
            res = payment_service.void_or_refund_charge(
                payment_id,
                reason="checkout database failure compensation",
                amount=fresh_attempt.amount,
                idempotency_key=fresh_attempt.refund_idempotency_key,
            )
            fresh_attempt = db.session.get(PaymentAttempt, attempt_id)
            fresh_attempt.refund_ref = res.get("refund_id")
            p_status = res.get("payment_status")
            expected_paise = rupees_to_paise(fresh_attempt.amount)
            actual_paise = res.get("amount_refunded")

            if p_status == "refunded":
                fresh_attempt.status = "refunded"
                fresh_attempt.unrefunded_amount = Decimal("0.00")
            elif p_status == "partial_refunded" or (
                actual_paise is not None and actual_paise < expected_paise
            ):
                fresh_attempt.status = "partial_refunded"
                unrefunded_paise = expected_paise - (actual_paise or 0)
                fresh_attempt.unrefunded_amount = paise_to_rupees(unrefunded_paise)
            elif p_status == "refund_pending":
                fresh_attempt.status = "refund_pending"
            elif p_status == "refund_failed":
                fresh_attempt.retry_count += 1
                if fresh_attempt.retry_count >= 3:
                    fresh_attempt.status = "manual_review"
                else:
                    fresh_attempt.status = "refund_failed"
            else:
                fresh_attempt.status = "manual_review"
            db.session.commit()
        except Exception as ref_err:
            log.exception(
                "Compensating refund failed after post-verification failure for %s: %s",
                payment_id,
                ref_err,
            )
            fresh_attempt = db.session.get(PaymentAttempt, attempt_id)
            fresh_attempt.retry_count += 1
            fresh_attempt.failure_reason = f"refund dispatch error: {ref_err}"
            if fresh_attempt.retry_count >= 3:
                fresh_attempt.status = "manual_review"
            else:
                fresh_attempt.status = "refund_failed"
            db.session.commit()

        raise OrderError(
            "ORDER_FAILED",
            "The order could not be completed. Please try again.",
            500,
        )

    # Step 6: If persisted state remains uncertain, preserve/escalate manual_review; do not refund
    if fresh_attempt and fresh_attempt.status != "completed":
        fresh_attempt.status = "manual_review"
        fresh_attempt.failure_reason = "post-verification outcome uncertain"
        db.session.commit()
    raise OrderError(
        "ORDER_UNCERTAIN",
        "Order outcome uncertain; flagged for manual review",
        500,
    )


def checkout(buyer_id, shipping_address, payment_token=None, idem_key=None,
             razorpay_order_id=None, razorpay_payment_id=None, razorpay_signature=None):
    address = _clean_address(shipping_address)
    mode, mock_token, rzp_order_id, rzp_payment_id, rzp_sig = _parse_payment_input(
        payment_token, razorpay_order_id, razorpay_payment_id, razorpay_signature
    )

    if mode == "mock":
        # Sprint 1 MockGateway execution path
        lines = _cart_lines(buyer_id, for_update=True)
        if not lines:
            raise OrderError("CART_EMPTY", "Your cart is empty", 400)
        items = [(line.product_id, line.quantity) for line in lines]
        charge = None
        try:
            prices = _current_prices(lines)
            total = round(sum(prices[pid] * qty for pid, qty in items), 2)
            lock_and_validate_stock(items)
            charge = payment_service.capture_charge(total, mock_token, idem_key)
            decrement_stock(items)
            order = _save_order(buyer_id, address, lines, prices, total, charge)
            db.session.commit()
        except OutOfStock as err:
            db.session.rollback()
            _refund(charge, "stock ran out during checkout")
            raise OrderError(
                "INSUFFICIENT_STOCK",
                f"'{err.title}' only has {err.available} unit(s) available",
                400,
            ) from err
        except PaymentError as err:
            db.session.rollback()
            raise OrderError(err.code, err.message, err.status) from err
        except OrderError:
            db.session.rollback()
            raise
        except Exception as err:
            db.session.rollback()
            _refund(charge, "order could not be saved")
            log.exception("Checkout failed")
            raise OrderError(
                "ORDER_FAILED",
                "The order could not be completed. Please try again.",
                500,
            ) from err

        try:
            invoice_service.create_invoice(order.order_id)
        except Exception:
            log.exception("Invoice creation failed for order %s", order.order_id)
        return _summary(order, charge)

    # Razorpay Test Mode execution path (SAD §4.3.2 Option A)
    # 1. Lock PaymentAttempt (FOR UPDATE)
    attempt = db.session.scalar(
        db.select(PaymentAttempt)
        .where(PaymentAttempt.razorpay_order_id == rzp_order_id)
        .with_for_update()
    )
    if attempt is None:
        raise OrderError("INVALID_ORDER", "Payment attempt not found", 400)

    # 2. Validate ownership and attempt status
    if attempt.buyer_id != buyer_id:
        raise OrderError("FORBIDDEN", "Unauthorized payment attempt", 403)

    if attempt.status == "completed":
        raise OrderError("ALREADY_COMPLETED", "Payment attempt has already been fulfilled", 409)

    if attempt.status not in ("created", "callback_received"):
        raise OrderError(
            "INVALID_ATTEMPT_STATE",
            f"Payment attempt is in '{attempt.status}' state",
            400,
        )

    # 3. Check for replayed payment ID across existing orders
    existing_payment = db.session.scalar(
        db.select(Payment).where(Payment.transaction_ref == rzp_payment_id)
    )
    if existing_payment is not None:
        raise OrderError("REPLAYED_PAYMENT", "Payment ID has already been used", 409)

    attempt.status = "callback_received"
    attempt.razorpay_payment_id = rzp_payment_id

    # 4. Lock parent Cart
    cart = db.session.scalar(
        db.select(Cart).where(Cart.cart_id == attempt.cart_id).with_for_update()
    )
    if cart is None:
        _compensate_stock_cart_failure(
            attempt.attempt_id, rzp_order_id, rzp_payment_id, rzp_sig,
            "CART_INVALID", "Cart not found", "cart missing during checkout"
        )

    # 5. Lock CartItems
    lines = db.session.scalars(
        db.select(CartItem).where(CartItem.cart_id == cart.cart_id).with_for_update()
    ).all()
    if not lines:
        _compensate_stock_cart_failure(
            attempt.attempt_id, rzp_order_id, rzp_payment_id, rzp_sig,
            "CART_EMPTY", "Cart is empty or already consumed", "cart empty during checkout"
        )

    # 6. Validate cart snapshot and hash
    try:
        prices = _current_prices(lines)
    except OrderError as err:
        _compensate_stock_cart_failure(
            attempt.attempt_id, rzp_order_id, rzp_payment_id, rzp_sig,
            err.code, err.message, f"product unavailable: {err.message}"
        )

    cart_hash, total_decimal = compute_cart_hash(cart.cart_id, lines, prices)
    if cart_hash != attempt.cart_hash or total_decimal != attempt.amount:
        _compensate_stock_cart_failure(
            attempt.attempt_id, rzp_order_id, rzp_payment_id, rzp_sig,
            "CART_MISMATCH", "Cart items or prices changed since payment order creation",
            "cart hash or amount mismatch"
        )

    # 7. Lock Inventory rows in ascending product_id order
    items = [(line.product_id, line.quantity) for line in lines]
    try:
        lock_and_validate_stock(items)
    except OutOfStock as err:
        _compensate_stock_cart_failure(
            attempt.attempt_id, rzp_order_id, rzp_payment_id, rzp_sig,
            "INSUFFICIENT_STOCK", f"'{err.title}' only has {err.available} unit(s) available",
            f"stock ran out for '{err.title}'"
        )

    # 8. External capture / verification while inventory locks are held (SAD §4.3.2 Option A)
    token_dict = {
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": rzp_payment_id,
        "razorpay_signature": rzp_sig,
    }
    charge = None
    try:
        charge = payment_service.capture_charge(attempt.amount, token_dict, idem_key)
    except PaymentError as err:
        db.session.rollback()
        raise OrderError(err.code, err.message, err.status) from err

    # 9. Decrement stock, create Order, OrderItem, Payment, delete CartItems, mark completed, commit
    # Unified post-verification recovery protocol closes database failure gap
    try:
        decrement_stock(items)
        order = _save_order(buyer_id, address, lines, prices, float(attempt.amount), charge)
        attempt.status = "completed"
        attempt.razorpay_payment_id = charge["transaction_ref"]
        db.session.commit()
    except Exception as post_ver_err:
        log.exception("Post-verification database failure during checkout: %s", post_ver_err)
        return _handle_post_verification_failure(buyer_id, attempt, charge)

    try:
        invoice_service.create_invoice(order.order_id)
    except Exception:
        log.exception("Invoice creation failed for order %s", order.order_id)

    return _summary(order, charge)
