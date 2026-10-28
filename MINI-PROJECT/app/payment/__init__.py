from flask import Blueprint

payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")
