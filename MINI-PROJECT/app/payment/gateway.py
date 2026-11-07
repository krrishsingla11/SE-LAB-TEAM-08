from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
import os
import re
import uuid

import requests

try:
    import razorpay
    from razorpay.errors import (
        BadRequestError,
        GatewayError,
        ServerError,
        SignatureVerificationError,
    )
except ImportError:  # pragma: no cover
    razorpay = None
    BadRequestError = GatewayError = ServerError = SignatureVerificationError = Exception

logger = logging.getLogger(__name__)

CARD_NUMBER = re.compile(r"^\d{12,19}$")

# SAD §4.3.2 Step 7: 3.0-second external gateway timeout requirement.
# Note on Requests timeout semantics vs strict wall-clock deadline (Review Finding F-01):
# In Requests/urllib3, a timeout tuple (connect, read) configures socket-level timeouts:
# - Connect timeout (1.0s): Maximum time allowed to establish TCP/TLS connection.
# - Read timeout (2.0s): Maximum socket inactivity delay between successive bytes received.
# Neither scalar (3.0) nor tuple (1.0, 2.0) guarantees an absolute wall-clock deadline
# if data trickles slowly across chunked responses, nor does it bound multiple requests.
# Within Python's synchronous requests/SDK architecture, preemptive wall-clock cancellation
# cannot be guaranteed without asynchronous I/O or platform-dependent signals.
# In accordance with SAD §4.3.2 Option A, external verification is executed while
# holding the inventory row-level locks, with SDK retries explicitly disabled and socket
# timeouts strictly applied to limit blocking duration.
DEFAULT_TIMEOUT = (1.0, 2.0)


def rupees_to_paise(amount) -> int:
    """Convert an amount in INR Rupees to paise using exact Decimal arithmetic.

    Rejects amounts with genuine precision beyond two decimal places (fractional paise),
    as well as non-positive or non-numeric amounts. Trailing zeros (e.g. '10.000') are accepted.
    """
    if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal, str)):
        raise PaymentError("INVALID_AMOUNT", "Amount must be a numeric value", 422)

    try:
        dec = Decimal(str(amount).strip())
    except Exception:
        raise PaymentError("INVALID_AMOUNT", "Invalid numeric amount", 422)

    if dec.is_nan() or dec.is_infinite():
        raise PaymentError("INVALID_AMOUNT", "Amount must be finite", 422)

    if dec <= 0:
        raise PaymentError("INVALID_AMOUNT", "Amount must be a positive number", 422)

    paise_dec = dec * Decimal("100")
    if paise_dec != paise_dec.to_integral_value():
        raise PaymentError(
            "INVALID_AMOUNT",
            f"Amount '{amount}' has fractional paise (precision exceeds two decimal places)",
            422,
        )

    return int(paise_dec)


def paise_to_rupees(paise: int) -> Decimal:
    """Convert an amount in paise to INR Rupees using exact Decimal arithmetic."""
    if isinstance(paise, bool) or not isinstance(paise, int) or paise < 0:
        raise PaymentError("INVALID_AMOUNT", "Paise amount must be a non-negative integer", 422)
    return (Decimal(paise) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PaymentError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class BasePaymentGateway(ABC):
    """Abstract payment gateway contract adhering to SAD §3.4.1 IPaymentContract."""

    @abstractmethod
    def capture_charge(self, amount, token, idem_key=None):
        """Authorize or capture a charge for the specified amount and token."""
        raise NotImplementedError

    @abstractmethod
    def void_or_refund_charge(self, txn_ref, reason=None, amount=None, idempotency_key=None):
        """Void or refund a previously captured charge."""
        raise NotImplementedError


class MockGateway(BasePaymentGateway):
    """Deterministic stand-in for the real gateway (Sprint 1)."""

    def __init__(self):
        self._captured = {}

    def capture_charge(self, amount, token, idem_key=None):
        if idem_key and idem_key in self._captured:
            return self._captured[idem_key]
        result = self._decide(amount, token)
        if idem_key:
            self._captured[idem_key] = result
        return result

    def _decide(self, amount, token):
        if not isinstance(token, str) or not token:
            raise PaymentError(
                "INVALID_TOKEN", "A payment token is required", 422)
        if CARD_NUMBER.match(re.sub(r"[\s-]", "", token)):
            raise PaymentError(
                "RAW_CARD_DATA_REJECTED",
                "Send a payment token, never a card number", 400)
        if token == "tok_charge_declined":
            raise PaymentError("CARD_DECLINED", "Card declined", 402)
        if token == "tok_timeout":
            raise PaymentError(
                "GATEWAY_TIMEOUT", "Payment gateway timed out", 504)
        if not token.startswith("tok_"):
            raise PaymentError("INVALID_TOKEN", "Unknown payment token", 422)
        return {
            "transaction_ref": "TXN-MOCK-" + uuid.uuid4().hex[:12].upper(),
            "payment_status": "captured",
            "amount": amount,
        }

    def void_or_refund_charge(self, txn_ref, reason=None, amount=None, idempotency_key=None):
        if not isinstance(txn_ref, str) or not txn_ref.strip():
            raise PaymentError(
                "INVALID_TOKEN", "Transaction reference is required for refund", 422
            )
        paise = None
        if amount is not None:
            paise = rupees_to_paise(amount)
        result = {
            "transaction_ref": txn_ref,
            "payment_status": "refunded",
            "refund_id": "rfnd_mock_" + uuid.uuid4().hex[:12],
            "refund_status": "processed",
            "amount_refunded": paise,
            "reason": reason,
        }
        if idempotency_key:
            result["idempotency_key"] = idempotency_key
        return result


class RazorpayGateway(BasePaymentGateway):
    """Razorpay Test Mode gateway adapter complying with IPaymentContract and SAD §4.3.2."""

    def __init__(self, key_id=None, key_secret=None, client=None, timeout=DEFAULT_TIMEOUT):
        raw_key_id = key_id if key_id is not None else os.getenv("RAZORPAY_KEY_ID")
        raw_key_secret = key_secret if key_secret is not None else os.getenv("RAZORPAY_KEY_SECRET")

        self.key_id = (raw_key_id or "").strip()
        self.key_secret = (raw_key_secret or "").strip()

        if not self.key_id or not self.key_secret:
            raise PaymentError(
                "GATEWAY_CONFIGURATION_ERROR",
                "Razorpay credentials not configured: RAZORPAY_KEY_ID and "
                "RAZORPAY_KEY_SECRET are required",
                500,
            )

        self.timeout = timeout
        if client is not None:
            self.client = client
        else:
            if razorpay is None:
                raise PaymentError(
                    "GATEWAY_CONFIGURATION_ERROR",
                    "The 'razorpay' package is not installed",
                    500,
                )
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

        # Disable automatic SDK retries to reduce additional network delay while
        # holding row locks. Note: (1.0, 2.0) socket timeout limits connect/read wait
        # per HTTP request, but is not an absolute three-second wall-clock deadline.
        if hasattr(self.client, "retry_enabled"):
            self.client.retry_enabled = False
        if hasattr(self.client, "max_retries"):
            self.client.max_retries = 1

    def __repr__(self):
        # Never leak secret keys in logs or string representations
        return f"<RazorpayGateway key_id='{self.key_id}'>"

    def verify_payment_signature(self, razorpay_order_id, razorpay_payment_id,
                                 razorpay_signature) -> bool:
        """Verify the payment signature returned by Razorpay Checkout."""
        if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
            raise PaymentError(
                "INVALID_SIGNATURE",
                "razorpay_order_id, razorpay_payment_id, and razorpay_signature are required",
                400,
            )
        try:
            params = {
                "razorpay_order_id": str(razorpay_order_id),
                "razorpay_payment_id": str(razorpay_payment_id),
                "razorpay_signature": str(razorpay_signature),
            }
            res = self.client.utility.verify_payment_signature(params)
            if res is False:
                raise PaymentError("INVALID_SIGNATURE", "Invalid payment signature", 400)
            return True
        except SignatureVerificationError as err:
            raise PaymentError("INVALID_SIGNATURE", "Invalid payment signature", 400) from err
        except PaymentError:
            raise
        except Exception as err:
            raise PaymentError(
                "INVALID_SIGNATURE", "Payment signature verification failed", 400
            ) from err

    def fetch_payment(self, payment_id: str) -> dict:
        """Retrieve payment details from Razorpay with timeout and error handling."""
        if not isinstance(payment_id, str) or not payment_id.strip():
            raise PaymentError("INVALID_TOKEN", "Payment ID is required", 422)
        clean_id = payment_id.strip()
        if CARD_NUMBER.match(re.sub(r"[\s-]", "", clean_id)):
            raise PaymentError(
                "RAW_CARD_DATA_REJECTED",
                "Send a payment token, never a card number",
                400,
            )

        try:
            return self.client.payment.fetch(clean_id, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.warning("Razorpay gateway timeout fetching payment %s", clean_id)
            raise PaymentError("GATEWAY_TIMEOUT", "Payment gateway timed out", 504) from None
        except BadRequestError as err:
            logger.warning(
                "Razorpay gateway bad request fetching payment %s: %s",
                clean_id,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_AUTHENTICATION_ERROR",
                "Payment gateway authentication or bad request error",
                502,
            ) from None
        except (GatewayError, ServerError, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as err:
            logger.warning(
                "Razorpay gateway communication error fetching payment %s: %s",
                clean_id,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_ERROR",
                "Payment gateway communication failed",
                502,
            ) from None
        except Exception as err:
            logger.error(
                "Unexpected error fetching payment %s: %s",
                clean_id,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_ERROR",
                "Unexpected error communicating with payment gateway",
                502,
            ) from None

    def verify_payment(self, payment_id: str, expected_amount,
                       expected_currency: str = "INR",
                       expected_order_id: str = None) -> dict:
        """Verify payment amount, currency, order_id, and captured status using exact Decimal."""
        payment = self.fetch_payment(payment_id)

        # 1. Order ID verification (when expected_order_id is provided)
        if expected_order_id:
            actual_order_id = str(payment.get("order_id", "") or "").strip()
            if actual_order_id != expected_order_id.strip():
                raise PaymentError(
                    "ORDER_MISMATCH",
                    f"Payment order ID mismatch: expected '{expected_order_id}', "
                    f"got '{actual_order_id}'",
                    400,
                )

        # 2. Amount verification using Decimal paise conversion
        expected_paise = rupees_to_paise(expected_amount)
        try:
            actual_paise = int(payment.get("amount", 0))
        except (ValueError, TypeError):
            actual_paise = 0

        if expected_paise != actual_paise:
            raise PaymentError(
                "AMOUNT_MISMATCH",
                f"Payment amount mismatch: expected {expected_paise} paise, got "
                f"{actual_paise} paise",
                400,
            )

        # 3. Currency verification
        actual_currency = str(payment.get("currency", "") or "").strip().upper()
        if actual_currency != expected_currency.strip().upper():
            raise PaymentError(
                "CURRENCY_MISMATCH",
                f"Payment currency mismatch: expected '{expected_currency}', "
                f"got '{actual_currency}'",
                400,
            )

        # 4. Captured status verification
        actual_status = str(payment.get("status", "") or "").strip().lower()
        if actual_status != "captured":
            raise PaymentError(
                "PAYMENT_NOT_CAPTURED",
                f"Payment is not captured: status is '{actual_status}'",
                400,
            )

        return payment

    def capture_charge(self, amount, token, idem_key=None) -> dict:
        """Verify payment and return standardized captured charge dictionary."""
        if not isinstance(token, (str, dict)) or not token:
            raise PaymentError("INVALID_TOKEN", "A payment token is required", 422)

        token_data = None
        if isinstance(token, str):
            clean_token = token.strip()
            if CARD_NUMBER.match(re.sub(r"[\s-]", "", clean_token)):
                raise PaymentError(
                    "RAW_CARD_DATA_REJECTED",
                    "Send a payment token, never a card number",
                    400,
                )

            if clean_token.startswith("{") and clean_token.endswith("}"):
                try:
                    token_data = json.loads(clean_token)
                except Exception:
                    raise PaymentError("INVALID_TOKEN", "Malformed JSON token", 422)
            elif "|" in clean_token:
                parts = clean_token.split("|")
                if len(parts) == 3:
                    token_data = {
                        "razorpay_order_id": parts[0].strip(),
                        "razorpay_payment_id": parts[1].strip(),
                        "razorpay_signature": parts[2].strip(),
                    }
                else:
                    raise PaymentError(
                        "INVALID_TOKEN",
                        "Pipe-delimited token must contain order_id|payment_id|signature",
                        422,
                    )
            else:
                # F-02: Bare payment IDs (including pay_...) are strictly rejected
                raise PaymentError(
                    "INVALID_TOKEN",
                    "Payment token must be a dict or JSON object containing "
                    "razorpay_order_id, razorpay_payment_id, and razorpay_signature",
                    422,
                )
        elif isinstance(token, dict):
            token_data = token

        if not isinstance(token_data, dict):
            raise PaymentError(
                "INVALID_TOKEN",
                "Payment token must be a dict or JSON object containing "
                "razorpay_order_id, razorpay_payment_id, and razorpay_signature",
                422,
            )

        order_id = str(token_data.get("razorpay_order_id", "") or "").strip()
        payment_id = str(token_data.get("razorpay_payment_id", "") or "").strip()
        signature = str(token_data.get("razorpay_signature", "") or "").strip()

        if not (order_id and payment_id and signature):
            raise PaymentError(
                "INVALID_TOKEN",
                "Missing razorpay_order_id, razorpay_payment_id, or razorpay_signature",
                422,
            )

        self.verify_payment_signature(order_id, payment_id, signature)
        self.verify_payment(
            payment_id,
            expected_amount=amount,
            expected_currency="INR",
            expected_order_id=order_id,
        )
        return {
            "transaction_ref": str(payment_id),
            "payment_status": "captured",
            "amount": amount,
        }

    def fetch_multiple_refund(self, payment_id: str) -> dict:
        """Retrieve all refunds for a payment from Razorpay."""
        if not isinstance(payment_id, str) or not payment_id.strip():
            raise PaymentError("INVALID_TOKEN", "Payment ID is required", 422)
        clean_id = payment_id.strip()
        try:
            return self.client.payment.fetch_multiple_refund(clean_id, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.warning("Razorpay gateway timeout fetching refunds for %s", clean_id)
            raise PaymentError("GATEWAY_TIMEOUT", "Payment gateway timed out", 504) from None
        except BadRequestError as err:
            logger.warning(
                "Razorpay gateway bad request fetching refunds for %s: %s",
                clean_id,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_AUTHENTICATION_ERROR",
                "Payment gateway authentication or bad request error fetching refunds",
                502,
            ) from None
        except (GatewayError, ServerError, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as err:
            logger.warning(
                "Razorpay gateway communication error fetching refunds for %s: %s",
                clean_id,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_ERROR",
                "Payment gateway communication failed fetching refunds",
                502,
            ) from None
        except Exception as err:
            logger.error(
                "Unexpected error fetching refunds for %s: %s",
                clean_id,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_ERROR",
                "Unexpected error communicating with payment gateway",
                502,
            ) from None

    def void_or_refund_charge(self, txn_ref: str, reason=None, amount=None,
                              idempotency_key=None) -> dict:
        """Issue a refund for a previously captured payment through Razorpay."""
        if not isinstance(txn_ref, str) or not txn_ref.strip():
            raise PaymentError(
                "INVALID_TOKEN", "Transaction reference is required for refund", 422
            )

        clean_ref = txn_ref.strip()
        refund_data = {}
        if amount is not None:
            # Validates that amount > 0, is numeric, and has no fractional paise
            refund_data["amount"] = rupees_to_paise(amount)
        if reason:
            refund_data["notes"] = {"reason": str(reason)[:255]}

        kwargs = {"timeout": self.timeout}
        if idempotency_key:
            kwargs["headers"] = {"X-Refund-Idempotency": str(idempotency_key).strip()}

        try:
            res = self.client.payment.refund(clean_ref, refund_data, **kwargs)
            if not isinstance(res, dict):
                logger.error("Razorpay refund returned non-dict response for %s", clean_ref)
                return {
                    "transaction_ref": clean_ref,
                    "payment_status": "manual_review",
                    "refund_id": None,
                    "refund_status": "unknown",
                    "amount_refunded": None,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                }

            refund_id = res.get("id")
            refund_status = str(res.get("status") or "").strip().lower()
            resp_payment_id = res.get("payment_id")

            # Validate returned entity belongs to the expected payment
            if resp_payment_id and str(resp_payment_id).strip() != clean_ref:
                logger.error(
                    "Refund entity payment_id mismatch: expected %s, got %s",
                    clean_ref,
                    resp_payment_id,
                )
                return {
                    "transaction_ref": clean_ref,
                    "payment_status": "manual_review",
                    "refund_id": refund_id,
                    "refund_status": "inconsistent",
                    "amount_refunded": None,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                }

            try:
                actual_paise = (
                    int(res.get("amount", 0)) if res.get("amount") is not None else None
                )
            except (ValueError, TypeError):
                actual_paise = None

            requested_paise = refund_data.get("amount")

            if refund_status == "processed":
                if requested_paise is not None:
                    if (
                        actual_paise is not None
                        and actual_paise < requested_paise
                    ):
                        final_payment_status = "partial_refunded"
                    elif (
                        actual_paise is not None
                        and actual_paise == requested_paise
                    ):
                        final_payment_status = "refunded"
                    else:
                        final_payment_status = "manual_review"
                else:
                    # requested_paise is None (full refund requested without explicit amount).
                    # Must establish actual outstanding payment amount from payment entity.
                    payment_data = None
                    try:
                        payment_data = self.client.payment.fetch(
                            clean_ref, timeout=self.timeout
                        )
                    except Exception as p_err:
                        logger.warning(
                            "Could not fetch payment %s to establish outstanding amount: %s",
                            clean_ref,
                            p_err,
                        )

                    if isinstance(payment_data, dict):
                        try:
                            total_captured = int(payment_data.get("amount", 0))
                        except (ValueError, TypeError):
                            total_captured = None
                        try:
                            total_refunded = int(payment_data.get("amount_refunded", 0))
                        except (ValueError, TypeError):
                            total_refunded = None
                        p_refund_status = str(
                            payment_data.get("refund_status") or ""
                        ).strip().lower()

                        if p_refund_status == "full" or (
                            total_captured is not None
                            and total_refunded is not None
                            and total_refunded >= total_captured
                            and total_captured > 0
                        ):
                            final_payment_status = "refunded"
                        elif p_refund_status == "partial" or (
                            total_captured is not None
                            and total_refunded is not None
                            and 0 < total_refunded < total_captured
                        ):
                            final_payment_status = "partial_refunded"
                        else:
                            final_payment_status = "manual_review"
                    else:
                        final_payment_status = "manual_review"
            elif refund_status == "pending":
                final_payment_status = "refund_pending"
            elif refund_status == "failed":
                final_payment_status = "refund_failed"
            else:
                final_payment_status = "manual_review"

            return {
                "transaction_ref": clean_ref,
                "payment_status": final_payment_status,
                "refund_id": refund_id,
                "refund_status": refund_status,
                "amount_refunded": actual_paise,
                "reason": reason,
                "idempotency_key": idempotency_key,
            }
        except requests.exceptions.Timeout:
            logger.warning("Razorpay gateway timeout refunding payment %s", clean_ref)
            raise PaymentError(
                "GATEWAY_TIMEOUT", "Payment gateway timed out during refund", 504
            ) from None
        except BadRequestError as err:
            logger.warning(
                "Razorpay gateway bad request refunding payment %s: %s",
                clean_ref,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_AUTHENTICATION_ERROR",
                "Payment gateway authentication or validation error during refund",
                502,
            ) from None
        except (GatewayError, ServerError, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as err:
            logger.warning(
                "Razorpay gateway communication error refunding payment %s: %s",
                clean_ref,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_ERROR",
                "Payment gateway communication failed during refund",
                502,
            ) from None
        except Exception as err:
            logger.error(
                "Unexpected error refunding payment %s: %s",
                clean_ref,
                type(err).__name__,
            )
            raise PaymentError(
                "GATEWAY_ERROR",
                "Unexpected error during refund",
                502,
            ) from None
