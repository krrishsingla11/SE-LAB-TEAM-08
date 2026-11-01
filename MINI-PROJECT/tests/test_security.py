"""Security tests for SE8-13: TC-SEC-01, TC-SEC-03, TC-SEC-04 (STP section 13.9).

TC-SEC-03 and TC-SEC-04 run against the Flask test app (see conftest.py).
TC-SEC-01 needs the real web server with a TLS certificate, so it only runs
when you set MARKETPLACE_HOST, for example:   set MARKETPLACE_HOST=localhost
"""
import base64
import http.client
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import User

PASSWORD = "StrongP@ss123"
HOST = os.environ.get("MARKETPLACE_HOST")
needs_server = pytest.mark.skipif(
    not HOST, reason="Set MARKETPLACE_HOST (e.g. localhost) to test a running TLS server"
)


# ---------------------------------------------------------------- helpers
def _register(client, role="buyer"):
    email = f"sec_{uuid.uuid4().hex[:8]}@pes.edu"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Sec Tester", "role": role},
    )
    assert resp.status_code == 201, resp.get_json()
    return email, resp.get_json().get("user_id")


def _make_token(user_id, role="buyer", **kwargs):
    """Create a valid token directly, so these tests do not need the login route."""
    return create_access_token(
        identity=str(user_id), additional_claims={"role": role}, **kwargs
    )


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text_value):
    return base64.urlsafe_b64decode(text_value + "=" * (-len(text_value) % 4))


def _claims(token):
    return json.loads(_unb64(token.split(".")[1]))


def _tamper_role(token, new_role="admin"):
    """Change the role inside the token but keep the old signature."""
    header, payload, signature = token.split(".")
    claims = json.loads(_unb64(payload))
    claims["role"] = new_role
    new_payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return ".".join([header, new_payload, signature])


def _protected_call(client, token):
    """Call a protected (Buyer-only) endpoint with the given token."""
    return client.post(
        "/api/cart/items",
        json={"product_id": 1, "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )


# ------------------------------------------------------------ TC-SEC-03
def test_tc_sec_03_password_stored_as_bcrypt_hash(client, caplog):
    """Password must be a bcrypt hash starting with $2b$12$; no plaintext anywhere."""
    caplog.set_level(logging.DEBUG)
    email, _ = _register(client)

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one()
    stored = user.password_hash

    assert stored is not None
    assert stored.startswith("$2b$12$")
    assert len(stored) == 60
    assert PASSWORD not in stored
    assert PASSWORD not in caplog.text


# ------------------------------------------------------------ TC-SEC-04
def test_tc_sec_04_login_token_lasts_24_hours(client):
    email, _ = _register(client)
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    if resp.status_code == 404:
        pytest.skip("Login route is not merged yet")
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    claims = _claims(body["token"])
    assert body["expires_in"] == 86400
    assert claims["exp"] - claims["iat"] == 86400


def test_tc_sec_04_tampered_role_token_returns_401(client):
    _, user_id = _register(client)
    token = _make_token(user_id)

    assert _protected_call(client, token).status_code != 401  # the real token is accepted
    resp = _protected_call(client, _tamper_role(token, "admin"))
    assert resp.status_code == 401  # 422 here means the JWT error handler is missing


def test_tc_sec_04_expired_token_returns_401(client):
    _, user_id = _register(client)
    expired = _make_token(user_id, expires_delta=timedelta(hours=-1))
    assert _protected_call(client, expired).status_code == 401


# ------------------------------------------------------------ TC-SEC-01
def _s_client(version_flag):
    exe = shutil.which("openssl")
    if exe is None:
        pytest.skip("openssl is not on PATH (Git for Windows has one in Git\\usr\\bin)")
    proc = subprocess.run(
        [exe, "s_client", "-connect", f"{HOST}:443", version_flag],
        input="", capture_output=True, text=True, timeout=30,
    )
    return proc.stdout + proc.stderr


def _handshake_ok(output):
    return "BEGIN CERTIFICATE" in output and "Cipher is (NONE)" not in output


@needs_server
def test_tc_sec_01_http_redirects_to_https():
    conn = http.client.HTTPConnection(HOST, 80, timeout=10)
    conn.request("GET", "/")
    resp = conn.getresponse()
    assert resp.status == 301
    assert resp.getheader("Location", "").startswith("https://")
    conn.close()


@needs_server
@pytest.mark.parametrize("flag", ["-tls1", "-tls1_1"])
def test_tc_sec_01_old_tls_versions_rejected(flag):
    output = _s_client(flag)
    if "no protocols available" in output or "unknown option" in output:
        pytest.skip("Local openssl cannot speak this old version; use nmap instead")
    assert not _handshake_ok(output)


@needs_server
@pytest.mark.parametrize("flag", ["-tls1_2", "-tls1_3"])
def test_tc_sec_01_modern_tls_versions_accepted(flag):
    assert _handshake_ok(_s_client(flag))
