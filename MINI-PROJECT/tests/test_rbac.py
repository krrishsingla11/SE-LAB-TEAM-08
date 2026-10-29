"""RBAC middleware tests (SE8-16). Uses a tiny Flask app, so it does not
need Kushal's app. Covers TC-AUTH-05 and TC-SEC-04 (401 for bad tokens)."""
from datetime import timedelta

import pytest

pytest.importorskip("flask_jwt_extended")

from flask import Flask  # noqa: E402
from flask_jwt_extended import JWTManager, create_access_token  # noqa: E402

from app.middleware.rbac import role_required  # noqa: E402


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = "test-secret-key-for-rbac-tests-1234567890"
    JWTManager(app)

    @app.route("/artisan-only")
    @role_required("artisan")
    def artisan_only():
        return {"ok": True}

    return app


def _token(app, role, **kw):
    with app.app_context():
        return create_access_token(identity="1", additional_claims={"role": role}, **kw)


def _get(app, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return app.test_client().get("/artisan-only", headers=headers)


def test_no_token_returns_401(app):
    assert _get(app).status_code == 401


def test_buyer_token_returns_403(app):
    r = _get(app, _token(app, "buyer"))
    assert r.status_code == 403
    assert r.get_json()["message"] == "Artisan privilege required"


def test_artisan_token_returns_200(app):
    assert _get(app, _token(app, "artisan")).status_code == 200


def test_tampered_token_returns_401(app):
    assert _get(app, _token(app, "artisan") + "x").status_code == 401


def test_expired_token_returns_401(app):
    token = _token(app, "artisan", expires_delta=timedelta(seconds=-1))
    assert _get(app, token).status_code == 401
