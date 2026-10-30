"""Authentication & RBAC tests (SE8-12 / SE8-14 / SE8-16) - STP section 13.1"""
from datetime import timedelta
import time

import bcrypt
from flask_jwt_extended import create_access_token, decode_token
import pytest

from app.models import User

SKIP = pytest.mark.skip(
    reason="Waiting for app skeleton / not implemented yet")


def test_tc_auth_01_valid_buyer_registration(client, app, db):
    """TC-AUTH-01 (High) - OMH-F-001
    Steps:    POST /api/auth/register with valid email, name, role=buyer.
    Expected: HTTP 201; user row in DB; password hashed with bcrypt.
    """
    payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Test Buyer",
        "role": "buyer",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201

    data = response.get_json()
    assert "user_id" in data
    assert data["email"] == "test_buyer@pes.edu"
    assert data["full_name"] == "Test Buyer"
    assert data["role"] == "buyer"

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "test_buyer@pes.edu")
        )
        assert user is not None
        assert user.full_name == "Test Buyer"
        assert user.role == "buyer"
        assert user.user_id == data["user_id"]
        # Verify password is not plaintext
        assert user.password_hash != "StrongP@ss123"
        assert user.password_hash.startswith("$2b$12$")


def test_tc_auth_02_duplicate_email_registration(client, app, db):
    """TC-AUTH-02 (High) - OMH-F-001
    Steps:    POST /api/auth/register again with the same email.
    Expected: HTTP 409; error 'Email already registered'; no duplicate row.
    """
    payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Test Buyer",
        "role": "buyer",
    }
    # Initial registration
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with identical email
    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    data2 = res2.get_json()
    assert data2.get("message") == "Email already registered"

    # Registration with case-variant email
    variant_payload = dict(payload, email="TEST_BUYER@PES.EDU")
    res3 = client.post("/api/auth/register", json=variant_payload)
    assert res3.status_code == 409
    data3 = res3.get_json()
    assert data3.get("message") == "Email already registered"

    with app.app_context():
        count = db.session.query(User).filter(User.email == "test_buyer@pes.edu").count()
        assert count == 1


def test_password_is_bcrypt_hash_and_verifiable(client, app, db):
    """OMH-SR-001 / TC-SEC-03: Stored password must be bcrypt hash ($2b$12$) and verifiable."""
    raw_password = "StrongP@ss123"
    payload = {
        "email": "artisan_secure@pes.edu",
        "password": raw_password,
        "full_name": "Secure Artisan",
        "role": "artisan",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "artisan_secure@pes.edu")
        )
        assert user is not None
        # Must start with $2b$12$
        assert user.password_hash.startswith("$2b$12$")
        assert len(user.password_hash) == 60
        # bcrypt verification succeeds with correct password
        assert bcrypt.checkpw(raw_password.encode("utf-8"), user.password_hash.encode("utf-8"))
        # bcrypt verification fails with wrong password
        assert not bcrypt.checkpw(b"WrongP@ss999", user.password_hash.encode("utf-8"))


def test_valid_artisan_registration(client, app, db):
    """Register user with artisan role."""
    payload = {
        "email": "clay_crafter@pes.edu",
        "password": "ArtisanPass123",
        "full_name": "Clay Crafter",
        "role": "artisan",
        "shop_name": "Clay Studio",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["role"] == "artisan"

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "clay_crafter@pes.edu")
        )
        assert user is not None
        assert user.role == "artisan"


@pytest.mark.parametrize(
    "invalid_payload,expected_err",
    [
        ({}, "Email is required"),
        ({"password": "Pass1234", "full_name": "A", "role": "buyer"}, "Email is required"),
        (
            {"email": "", "password": "Pass1234", "full_name": "A", "role": "buyer"},
            "Email is required",
        ),
        (
            {
                "email": "not-an-email",
                "password": "Pass1234",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Invalid email format",
        ),
        (
            {"email": "valid@pes.edu", "full_name": "Valid Name", "role": "buyer"},
            "Password is required",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "short",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "alllowercaseno1",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "ALLUPPERCASENO1",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "NoDigitsAtAllHere",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {"email": "valid@pes.edu", "password": "StrongP@ss123", "role": "buyer"},
            "Full name is required",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "StrongP@ss123",
                "full_name": "X",
                "role": "buyer",
            },
            "Full name must be between 2 and 120 characters",
        ),
        (
            {"email": "valid@pes.edu", "password": "StrongP@ss123", "full_name": "Valid Name"},
            "Role is required",
        ),
    ],
)
def test_registration_missing_or_malformed_fields(client, invalid_payload, expected_err):
    """Missing or malformed input must return HTTP 400 with a descriptive error."""
    res = client.post("/api/auth/register", json=invalid_payload)
    assert res.status_code == 400
    data = res.get_json()
    assert expected_err in data["message"]


def test_registration_empty_body(client):
    """Submitting empty or non-JSON body must return HTTP 400."""
    res = client.post("/api/auth/register", data="not json", content_type="text/plain")
    assert res.status_code == 400


def test_registration_invalid_or_unauthorized_roles(client, app, db):
    """Registration with unauthorized 'admin' role or invalid role must be rejected."""
    # Attempting to register as admin (privilege escalation)
    admin_payload = {
        "email": "hacker@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Hacker Admin",
        "role": "admin",
    }
    res_admin = client.post("/api/auth/register", json=admin_payload)
    assert res_admin.status_code in (400, 403)
    assert "administrator" in res_admin.get_json()["message"].lower()

    # Verify no admin user was created in DB
    with app.app_context():
        admin_user = db.session.scalar(
            db.select(User).where(User.email == "hacker@pes.edu")
        )
        assert admin_user is None

    # Invalid role
    res_invalid = client.post(
        "/api/auth/register",
        json={
            "email": "invalid_role@pes.edu",
            "password": "StrongP@ss123",
            "full_name": "Invalid Role",
            "role": "superman",
        },
    )
    assert res_invalid.status_code == 400
    assert "role" in res_invalid.get_json()["message"].lower()


def test_registration_response_does_not_expose_password_or_hash(client):
    """Responses must never expose plaintext password or password hash."""
    payload = {
        "email": "safe_user@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Safe User",
        "role": "buyer",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201

    data = res.get_json()
    assert "password" not in data
    assert "password_hash" not in data
    assert "StrongP@ss123" not in res.get_data(as_text=True)
    assert "$2b$" not in res.get_data(as_text=True)


def test_registration_normalizes_email(client, app, db):
    """Email must be trimmed and converted to lowercase."""
    payload = {
        "email": "   User.Normalized@PES.EDU   ",
        "password": "StrongP@ss123",
        "full_name": "Normalized User",
        "role": "buyer",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    assert res.get_json()["email"] == "user.normalized@pes.edu"

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "user.normalized@pes.edu")
        )
        assert user is not None
        assert user.email == "user.normalized@pes.edu"


def test_tc_auth_03_login_returns_jwt(client, app):
    """TC-AUTH-03 (High) - OMH-F-002
    Steps:    POST /api/auth/login with valid credentials; decode the JWT.
    Expected: HTTP 200; token returned; payload has user_id, role='buyer', exp=24 hours.
    """
    payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Test Buyer",
        "role": "buyer",
    }
    res_reg = client.post("/api/auth/register", json=payload)
    assert res_reg.status_code == 201
    user_id = res_reg.get_json()["user_id"]

    login_payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
    }
    before_login = time.time()
    res_login = client.post("/api/auth/login", json=login_payload)
    after_login = time.time()

    assert res_login.status_code == 200
    data = res_login.get_json()
    assert "token" in data
    assert "access_token" in data
    token = data["token"]
    assert isinstance(token, str)

    # Validate non-sensitive user summary in response
    assert data["user_id"] == user_id
    assert data["email"] == "test_buyer@pes.edu"
    assert data["full_name"] == "Test Buyer"
    assert data["role"] == "buyer"
    assert "password" not in data
    assert "password_hash" not in data

    # Verify JWT payload claims and 24-hour expiration
    with app.app_context():
        decoded = decode_token(token)
        assert decoded["sub"] == str(user_id)
        assert decoded["user_id"] == user_id
        assert decoded["role"] == "buyer"

        # Expiry is exactly 24 hours (86400 seconds) after issuance
        assert decoded["exp"] - decoded["iat"] == 86400
        assert before_login + 86400 - 5 <= decoded["exp"] <= after_login + 86400 + 5


def test_tc_auth_04_login_wrong_password(client):
    """TC-AUTH-04 (High) - OMH-F-002
    Steps:    POST /api/auth/login with a wrong password.
    Expected: HTTP 401; error 'Invalid credentials'; no token issued.
    """
    payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Test Buyer",
        "role": "buyer",
    }
    client.post("/api/auth/register", json=payload)

    wrong_pw_payload = {
        "email": "test_buyer@pes.edu",
        "password": "WrongPassword999",
    }
    response = client.post("/api/auth/login", json=wrong_pw_payload)
    assert response.status_code == 401
    data = response.get_json()
    assert data.get("message") == "Invalid credentials"
    assert "token" not in data
    assert "access_token" not in data


def test_login_unknown_email_returns_401(client):
    """Unknown email returns generic HTTP 401 without disclosing account non-existence."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent_user@pes.edu", "password": "StrongP@ss123"},
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data.get("message") == "Invalid credentials"
    assert "token" not in data
    assert "access_token" not in data


@pytest.mark.parametrize(
    "invalid_payload,expected_err",
    [
        ({}, "Email is required"),
        ({"email": "   ", "password": "Pass"}, "Email is required"),
        ({"email": 123, "password": "Pass"}, "Email is required"),
        ({"email": "valid@pes.edu"}, "Password is required"),
        ({"email": "valid@pes.edu", "password": ""}, "Password is required"),
        ({"email": "valid@pes.edu", "password": None}, "Password is required"),
    ],
)
def test_login_missing_or_invalid_fields(client, invalid_payload, expected_err):
    """Missing or incorrectly typed login fields return HTTP 400."""
    response = client.post("/api/auth/login", json=invalid_payload)
    assert response.status_code == 400
    data = response.get_json()
    assert expected_err in data["message"]


def test_login_normalizes_email(client):
    """Login email must be trimmed and lowercased to match registered credentials."""
    reg_payload = {
        "email": "user.normalized@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Normalized User",
        "role": "buyer",
    }
    client.post("/api/auth/register", json=reg_payload)

    login_payload = {
        "email": "   USER.NORMALIZED@PES.EDU   ",
        "password": "StrongP@ss123",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    assert "token" in response.get_json()


def test_login_derives_role_exclusively_from_database(client, app):
    """Client cannot escalate role via the login payload; role is derived from DB."""
    reg_payload = {
        "email": "regular_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Regular Buyer",
        "role": "buyer",
    }
    client.post("/api/auth/register", json=reg_payload)

    # Malicious client attempts to pass role='admin'
    login_payload = {
        "email": "regular_buyer@pes.edu",
        "password": "StrongP@ss123",
        "role": "admin",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["role"] == "buyer"

    with app.app_context():
        decoded = decode_token(data["token"])
        assert decoded["role"] == "buyer"


def test_jwt_tampered_token_returns_401(client, app):
    """Protected endpoint with tampered token signature returns HTTP 401."""
    with app.app_context():
        valid_token = create_access_token(
            identity="1",
            additional_claims={"user_id": 1, "role": "buyer"},
        )
    tampered_token = valid_token + "tampered"
    response = client.get("/api/cart", headers={"Authorization": f"Bearer {tampered_token}"})
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "INVALID_TOKEN"
    assert "timestamp" in data
    assert data["status_code"] == 401


def test_jwt_expired_token_returns_401(client, app):
    """Protected endpoint with an expired token returns HTTP 401."""
    with app.app_context():
        expired_token = create_access_token(
            identity="1",
            expires_delta=timedelta(seconds=-1),
            additional_claims={"user_id": 1, "role": "buyer"},
        )
    response = client.get("/api/cart", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "TOKEN_EXPIRED"
    assert data["message"] == "Token has expired"
    assert data["status_code"] == 401
    assert "timestamp" in data


def test_jwt_missing_token_returns_401(client):
    """Protected endpoint without an Authorization header returns HTTP 401."""
    response = client.get("/api/cart")
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "UNAUTHORIZED"
    assert data["status_code"] == 401
    assert "timestamp" in data


@SKIP
def test_tc_auth_05_rbac_denies_buyer_on_artisan_route():
    """TC-AUTH-05 (High) - OMH-F-003
    Steps:    GET /api/seller/dashboard with a Buyer JWT.
    Expected: HTTP 403; error 'Artisan privilege required'.
    """
    pass


@SKIP
def test_tc_auth_06_password_reset_flow():
    """TC-AUTH-06 (Medium) - OMH-F-004
    Steps:    POST /api/auth/reset-password; take token from Mailtrap;
          POST /api/auth/reset-password/confirm.
    Expected: HTTP 200; password updated; login with new password works. (SE8-17 stretch)
    """
    pass


@SKIP
def test_tc_auth_07_password_reset_expired_token():
    """TC-AUTH-07 (Medium) - OMH-F-004
    Steps:    Submit a token older than 15 minutes to /api/auth/reset-password/confirm.
    Expected: HTTP 400; error 'Reset token has expired'; password unchanged. (SE8-17 stretch)
    """
    pass
