import re
import uuid

CARD_NUMBER = re.compile(r"^\d{12,19}$")


class PaymentError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class MockGateway:
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

    def void_or_refund_charge(self, txn_ref, reason):
        return {"transaction_ref": txn_ref, "payment_status": "refunded",
                "reason": reason}
 