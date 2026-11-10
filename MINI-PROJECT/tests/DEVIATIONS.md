# Deviations and test results (Sprint 1 and 2)

Prepared by Kishan K Shenoy (QA Lead), Team 08. Updated 9 Nov 2026.

## Test environment

Run on a laptop with the Flask development server and SQLite. localhost adds a ~2 second IPv6 delay on Windows, so 127.0.0.1 was used.

- Windows laptop, Python 3.12, Flask development server (Werkzeug 3.1.9), SQLite database (load_test.db), JMeter 5.6.3 on Java 1.8
- JMeter ran on the same laptop as the app, so both shared the same CPU
- Test data from seed_demo.py (buyer@demo.test, Ceramic Vase, Silk Scarf)

## A. Deviations confirmed in the code

| # | Area | Specification says | Actual behaviour | Action |
|---|------|--------------------|------------------|--------|
| A1 | Password reset (F-004) | SAD: 404 for an unknown email | 404 is returned, so a person can check which emails are registered | Accept for the demo; for production return 200 always |
| A2 | Password reset token | SRS: random, time-limited token | Signed token that expires in 15 minutes and works once (no DB table) | Accept; note in the report |
| A3 | Login rate limit (SR-004) | STP TC-SEC-06: 6 failures in 2 minutes. SRS: 5 attempts in 10 minutes | 5 failures per IP in a 10-minute window, then 429 | Accept; align the STP wording with the SRS |
| A4 | Rate limit storage | - | Counters are in memory: lost on restart, not shared between workers; behind a proxy all users share one IP | Use a shared store before production |
| A5 | Audit logging (SR-005) | STP TC-SEC-07: log login, product creation, checkout | Only routes listed in `AUDIT_EVENTS` are logged; a new route must be added | Accept |
| A6 | Cart routes | SAD table lists only POST /api/cart/items | GET /api/cart, PUT and DELETE /api/cart/items/{id} also exist (the STP uses them) | Update the SAD |
| A7 | Payment (mock) | STP: POST /api/checkout, reference TXN-MOCK-OK | Charge route is POST /api/payments/charge; reference is TXN-MOCK-... | Align the STP |
| A8 | Payment gateway | STP describes only the mock gateway | Razorpay sandbox gateway was added (SE8-31), selected with PAYMENT_GATEWAY | Update the STP |
| A9 | Idempotency (TC-PAY-03) | Retry gives the same result | Works, but keys are kept in memory only | Accept for the stub gateway |
| A10 | Secrets | No default secrets in code | JWT secret defaults to `dev-only-change-me`; PyJWT warns that this key is 18 bytes, below the 32-byte minimum (seen when running seed_demo.py); DB URL default contains the password `postgres` | Set real values through environment variables |
| A11 | Product delete | SAD: delete product | DELETE soft-deletes (is_active = false) | Accept |
| A12 | Order status (TC-ORD-02, TC-ORD-03) | PUT /api/orders/{id}/status; email to the buyer | Route does not exist in main (route list checked 7 Nov) | Not built; test is marked xfail |
| A13 | Sales reports (TC-RPT-01, TC-RPT-02) | GET /api/reports/sales and /api/reports/export (CSV, PDF) | Routes do not exist in main | Not built; tests are marked xfail |
| A14 | Low-stock alert (TC-INV-02) | GET /api/seller/dashboard shows a low-stock badge | No dashboard API route in main (the dashboard page is frontend only) | Not built; test is marked xfail |
| A15 | Race condition (TC-INV-01) | 2 simultaneous checkouts, 1 unit | Test exists (SE8-29) but runs only with CHECKOUT_TEST_DATABASE_URL (PostgreSQL) | Run once with the docker-compose test profile |
| A16 | TLS (TC-SEC-01) | HTTP redirects to HTTPS; TLS 1.2+ only | No TLS server in the project, so the test is skipped | Not executed; document |
| A17 | Capacity (TC-PERF-02) | 500 users without 502/503 errors | 34.46% of requests failed in the 500-user run (see B1) | Re-run on a production-like stack; see C1 |

## B. Test results

### B1. Performance and uptime (JMeter plan `tests/performance/marketplace_load_test.jmx`)

| Test case | Target | Result | Status |
|-----------|--------|--------|--------|
| TC-OPS-01 health (`health_monitor.py`) | 99.5% of pings are 200 with database connected | 30 of 30 pings up, uptime 100.00%, 4 to 82 ms | PASS |
| TC-PERF-01 (100 users, 5 min) | 95th percentile <= 500 ms, 0% errors | 27,335 requests, 91.45 requests/s, average 34.20 ms, median 24 ms, 95th percentile 85 ms, 99th percentile 169.99 ms, maximum 971 ms, 0 errors (0.00%). The login request alone is slower (100 requests, average 866 ms, 95th percentile 938 ms) because bcrypt is slow on purpose; each user logs in once | PASS |
| TC-PERF-02 (500 users, 5 min) | No crash, no 502/503 errors | 47,319 requests, 156.4 requests/s, average 1,537 ms, maximum 4,220 ms, 16,307 errors (34.46%). No errors up to about 290 active users; errors began between 290 and 416 users and stayed at about 40% per 30 seconds at 500 users. Throughput stopped growing at about 180 requests/s. Error types: 15,645 connection refused (127.0.0.1:5000), 662 HTTP 401 Unauthorized | FAIL |

Possible causes (not confirmed): single-process Flask development server, SQLite, and JMeter on the same laptop. A production server (gunicorn) with PostgreSQL has not been tested.

### B2. Functional and security tests (pytest)

Last full run on main (9 Nov 2026): 266 tests, 251 passed, 11 skipped, 4 expected failures (xfail), 0 failed; flake8 clean.

| Test case | Result | Evidence |
|-----------|--------|----------|
| TC-AUTH-01 to 05 | PASS | tests/test_auth.py |
| TC-AUTH-06, TC-AUTH-07 (password reset) | PASS | tests/test_reset.py, 7 tests |
| TC-CART-01 to 03, TC-CHK-01 | PASS | tests/test_cart.py (TC-CHK-01 tested at cart level) |
| TC-PAY-01 to 03 | PASS | tests/test_payment.py |
| TC-SEC-03 (bcrypt hash), TC-SEC-04 (tampered, expired token) | PASS | tests/test_security.py |
| TC-SEC-06 (login rate limit) | PASS | tests/test_rate_limit.py, 7 tests |
| TC-SEC-07 (audit log) | PASS | tests/test_audit_log.py, 7 tests; log lines have a UTC timestamp and user id, password and payment_token show as *** |
| TC-INV-03 (invoice PDF and its contents), TC-INV-04 (other buyer gets 403), order history | PASS | tests/test_sprint2.py with PyMuPDF installed: 7 passed |
| TC-ORD-02, TC-ORD-03, TC-INV-02, TC-RPT-01, TC-RPT-02 | NOT BUILT | tests/test_sprint2.py: 4 xfailed (A12 to A14) |
| TC-INV-01 (race condition) | NOT EXECUTED | Needs the PostgreSQL test profile (A15) |
| TC-SEC-01 (HTTPS, TLS) | NOT EXECUTED | No TLS server (A16) |
| TC-SEC-05 (input sanitising) | NOT EXECUTED | No test written yet |
| OWASP ZAP scan | NOT EXECUTED | |
| TC-UX-01 (axe-core accessibility) | PENDING | Namith, SE8-41 |

## C. Open actions

| # | Action | Owner |
|---|--------|-------|
| C1 | Re-run the 500-user test on gunicorn and PostgreSQL (docker compose) and fix the cause of the errors | Krrish, Kushal, Kishan |
| C2 | Decide whether order status, sales reports and the seller dashboard API are in scope; if yes, build them | Krrish |
| C3 | Run TC-INV-01 with the PostgreSQL test profile | Kushal, Kishan |
| C4 | Write the TC-SEC-05 sanitising test and run the ZAP scan | Kishan |
| C5 | Set up TLS and run TC-SEC-01 | Krrish |
| C6 | Send the axe-core result for TC-UX-01 | Namith |
| C7 | Replace the default JWT secret and database password with environment variables | Kushal |
