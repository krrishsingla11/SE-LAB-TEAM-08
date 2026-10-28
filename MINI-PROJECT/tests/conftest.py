"""Shared test setup (SE8-12).

TODO once Kushal's skeleton is merged:
  1. create the test app (app factory) and a test client
  2. create the test DB fixture (isolated DB, rollback after each test)
  3. add helper fixtures: buyer_token, artisan_token, mock payment tokens
"""
import pytest


@pytest.fixture
def client():
    pytest.skip("Test app not available yet")


@pytest.fixture
def db():
    pytest.skip("Test DB not available yet")