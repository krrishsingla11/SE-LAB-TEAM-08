"""Code (line) coverage tests for electricity_bill.py  -  Lab 6.

How to run (from this folder):
    coverage run -m pytest CodeCoverageTest_electricity_bill.py
    coverage report -m

Goal: execute every line of electricity_bill.py at least once (>= 90% line coverage).
"""
import pytest
from electricity_bill import energy_charge, late_fee, subsidy


# ---------------------------------------------------------------- energy_charge
def test_low_usage_domestic():
    # slab 1: 50 units * 3 = 150, + fixed charge 50
    assert energy_charge(50, "domestic") == 200


def test_unknown_connection_raises():
    with pytest.raises(ValueError):
        energy_charge(50, "industrial")


def test_negative_units_raises():
    with pytest.raises(ValueError):
        energy_charge(-5, "domestic")


def test_mid_usage_domestic():
    # slab 2: 300 + (200 - 100) * 5 = 800, + fixed charge 50
    assert energy_charge(200, "domestic") == 850


def test_high_usage_domestic():
    # slab 3: 1300 + (400 - 300) * 8 = 2100, + fixed charge 50
    assert energy_charge(400, "domestic") == 2150


def test_commercial_connection_doubles_charge():
    # (50 * 3) * 2 = 300, + commercial fixed charge 150
    assert energy_charge(50, "commercial") == 450


# -------------------------------------------------------------------- late_fee
def test_paid_on_time():
    assert late_fee(500, 0) == 0


def test_late_up_to_15_days():
    assert late_fee(500, 10) == 50


def test_late_over_15_days_large_bill():
    # 100 flat + 3000 // 20 = 150 extra for bills above 2000
    assert late_fee(3000, 20) == 250


# --------------------------------------------------------------------- subsidy
def test_senior_low_usage_subsidy():
    assert subsidy(50, True, False) == 50


def test_solar_with_high_usage_gets_no_subsidy():
    # solar adds 100, but usage above 300 units cancels the subsidy
    assert subsidy(400, False, True) == 0
