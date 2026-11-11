"""Branch coverage tests for electricity_bill.py  -  Lab 6.

How to run (from this folder):
    coverage run --branch -m pytest BranchCoverageTest_electricity_bill.py
    coverage report -m

Goal: make every decision (if / elif) evaluate to BOTH True and False
(>= 90% branch coverage), including the boundary values of each condition.
"""
import pytest
from electricity_bill import energy_charge, late_fee, subsidy


# ---------------------------------------------------------------- energy_charge
@pytest.mark.parametrize(
    "units, connection, expected",
    [
        # slab 1 (units <= 100: 3 per unit) and its upper boundary
        (0, "domestic", 50),        # 0 * 3 + 50
        (50, "domestic", 200),      # 150 + 50
        (100, "domestic", 350),     # 300 + 50  (last unit of slab 1)
        # slab 2 (101..300: 300 + 5 per unit above 100) and its boundaries
        (101, "domestic", 355),     # 300 + 5 + 50
        (200, "domestic", 850),     # 300 + 500 + 50
        (300, "domestic", 1350),    # 300 + 1000 + 50  (last unit of slab 2)
        # slab 3 (units > 300: 1300 + 8 per unit above 300)
        (301, "domestic", 1358),    # 1300 + 8 + 50
        (400, "domestic", 2150),    # 1300 + 800 + 50
        # commercial connection: slab charge doubled, fixed charge 150
        (50, "commercial", 450),    # (150 * 2) + 150
        (150, "commercial", 1250),  # (550 * 2) + 150
        (500, "commercial", 5950),  # (2900 * 2) + 150
    ],
)
def test_energy_charge_slabs(units, connection, expected):
    assert energy_charge(units, connection) == expected


def test_unknown_connection_raises():
    with pytest.raises(ValueError, match="unknown connection"):
        energy_charge(50, "industrial")


def test_connection_name_is_case_sensitive():
    with pytest.raises(ValueError, match="unknown connection"):
        energy_charge(50, "Domestic")


def test_unknown_connection_is_checked_before_units():
    # both arguments are invalid: the connection check comes first
    with pytest.raises(ValueError, match="unknown connection"):
        energy_charge(-1, "industrial")


@pytest.mark.parametrize("connection", ["domestic", "commercial"])
def test_negative_units_raises(connection):
    with pytest.raises(ValueError, match="invalid units"):
        energy_charge(-1, connection)


# -------------------------------------------------------------------- late_fee
@pytest.mark.parametrize(
    "bill_amount, days_late, expected",
    [
        (500, 0, 0),      # paid on time          (days_late <= 0 is True)
        (500, -3, 0),     # paid early            (days_late <= 0 is True)
        (500, 1, 50),     # 1 day late            (<= 15 days)
        (500, 15, 50),    # boundary: 15 days still the small fee
        (500, 16, 100),   # boundary: 16 days -> 100 flat
        (2000, 20, 100),  # boundary: bill of exactly 2000 -> no extra fee
        (2001, 20, 200),  # 100 + 2001 // 20 = 100 + 100
        (3000, 20, 250),  # 100 + 3000 // 20 = 100 + 150
        (3000, 15, 50),   # large bill but within 15 days -> no extra fee
    ],
)
def test_late_fee(bill_amount, days_late, expected):
    assert late_fee(bill_amount, days_late) == expected


# --------------------------------------------------------------------- subsidy
@pytest.mark.parametrize(
    "units, is_senior, has_solar, expected",
    [
        # senior subsidy (units <= 100 and is_senior): both parts True / False
        (100, True, False, 50),     # boundary: exactly 100 units
        (101, True, False, 0),      # just above 100 units
        (50, False, False, 0),      # low usage but not a senior
        (301, True, False, 0),      # high usage, senior, no solar
        # solar subsidy (+100) and the "units > 300" cancellation
        (50, False, True, 100),     # solar only
        (200, False, True, 100),    # solar, units <= 300 -> keeps the 100
        (300, False, True, 100),    # boundary: 300 units still keeps it
        (301, False, True, 0),      # boundary: 301 units cancels everything
        (400, False, True, 0),      # solar with high usage
        # senior and solar together
        (100, True, True, 150),     # 50 + 100
        (400, True, True, 0),       # cancelled by high usage
    ],
)
def test_subsidy(units, is_senior, has_solar, expected):
    assert subsidy(units, is_senior, has_solar) == expected
