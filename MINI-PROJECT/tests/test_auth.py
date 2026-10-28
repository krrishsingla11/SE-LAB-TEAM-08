"""Authentication & RBAC tests (SE8-12 / SE8-16) - STP section 13.1"""
import pytest

SKIP = pytest.mark.skip(reason="Waiting for app skeleton / not implemented yet")

@SKIP
def test_tc_auth_01_valid_buyer_registration():
    """TC-AUTH-01 (High) - OMH-F-001
    Steps:    POST /api/auth/register with valid email, name, role=buyer.
    Expected: HTTP 201; user row in DB; password hashed with bcrypt; welcome email in Mailtrap.
    """
    pass

@SKIP
def test_tc_auth_02_duplicate_email_registration():
    """TC-AUTH-02 (High) - OMH-F-001
    Steps:    POST /api/auth/register again with the same email.
    Expected: HTTP 409; error 'Email already registered'; no duplicate row.
    """
    pass

@SKIP
def test_tc_auth_03_login_returns_jwt():
    """TC-AUTH-03 (High) - OMH-F-002
    Steps:    POST /api/auth/login with valid credentials; decode the JWT.
    Expected: HTTP 200; token returned; payload has user_id, role='buyer', exp=24 hours.
    """
    pass

@SKIP
def test_tc_auth_04_login_wrong_password():
    """TC-AUTH-04 (High) - OMH-F-002
    Steps:    POST /api/auth/login with a wrong password.
    Expected: HTTP 401; error 'Invalid credentials'; no token issued.
    """
    pass

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
    Steps:    POST /api/auth/reset-password; take token from Mailtrap; POST /api/auth/reset-password/confirm.
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