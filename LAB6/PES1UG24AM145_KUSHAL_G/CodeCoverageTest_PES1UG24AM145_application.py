"""
Code Coverage Test Suite for Gym Membership Application
Student: Kushal G
SRN: PES1UG24AM145
Scenario: Gym Membership
Application Module: gym_membership.py

This test suite comprehensively exercises every executable statement and function
in gym_membership.py to achieve complete code (line) coverage.
"""

import pytest
from gym_membership import PLAN_PRICE, membership_cost, can_enter, bmi_category


# ---------------------------------------------------------------------------
# Tests for PLAN_PRICE configuration
# ---------------------------------------------------------------------------

def test_plan_price_mapping():
    """Verify that standard subscription tiers exist with expected base prices."""
    assert PLAN_PRICE == {"monthly": 1500, "quarterly": 4000, "yearly": 12000}


# ---------------------------------------------------------------------------
# Tests for membership_cost function
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_plan", ["daily", "weekly", "lifetime", "", "MONTHLY", "unknown"])
def test_membership_cost_unknown_plan_raises_error(invalid_plan):
    """Unknown or invalid plan names must raise ValueError('unknown plan')."""
    with pytest.raises(ValueError, match="unknown plan"):
        membership_cost(invalid_plan, 25, False, False)


@pytest.mark.parametrize("too_young_age", [13, 10, 5, 0, -1])
def test_membership_cost_age_below_14_raises_error(too_young_age):
    """Members below age 14 must raise ValueError('too young')."""
    with pytest.raises(ValueError, match="too young"):
        membership_cost("monthly", too_young_age, False, False)


@pytest.mark.parametrize(
    "plan,age,expected",
    [
        ("monthly", 14, 1500),    # Lower boundary age
        ("monthly", 30, 1500),    # Adult
        ("monthly", 59, 1500),    # Upper non-senior boundary
        ("quarterly", 14, 4000),
        ("quarterly", 35, 4000),
        ("quarterly", 59, 4000),
        ("yearly", 14, 12000),
        ("yearly", 40, 12000),
        ("yearly", 59, 12000),
    ],
)
def test_membership_cost_standard_rates_no_discounts(plan, age, expected):
    """Standard pricing without senior or student discounts and without trainer."""
    assert membership_cost(plan, age, is_student=False, with_trainer=False) == expected


@pytest.mark.parametrize(
    "plan,age,is_student,expected",
    [
        ("monthly", 60, False, 1125),   # 1500 - 375 (25% off)
        ("monthly", 70, False, 1125),
        ("quarterly", 60, False, 3000), # 4000 - 1000 (25% off)
        ("quarterly", 80, False, 3000),
        ("yearly", 60, False, 9000),    # 12000 - 3000 (25% off)
        ("yearly", 65, True, 9000),     # Senior discount takes precedence over student
    ],
)
def test_membership_cost_senior_discount(plan, age, is_student, expected):
    """Senior discount of 25% applies to age >= 60 and overrides student discount."""
    assert membership_cost(plan, age, is_student, with_trainer=False) == expected


@pytest.mark.parametrize(
    "plan,age,expected",
    [
        ("monthly", 14, 1350),   # 1500 - 150 (10% off)
        ("monthly", 22, 1350),
        ("monthly", 59, 1350),
        ("quarterly", 14, 3600), # 4000 - 400 (10% off)
        ("quarterly", 21, 3600),
        ("yearly", 14, 10800),   # 12000 - 1200 (10% off)
        ("yearly", 25, 10800),
    ],
)
def test_membership_cost_student_discount(plan, age, expected):
    """Student discount of 10% applies to students under age 60."""
    assert membership_cost(plan, age, is_student=True, with_trainer=False) == expected


@pytest.mark.parametrize(
    "plan,age,is_student,expected",
    [
        ("monthly", 30, False, 3500),    # 1500 + 2000
        ("quarterly", 30, False, 6000),  # 4000 + 2000
        ("yearly", 30, False, 13500),    # 12000 + 2000 - 500 (yearly trainer rebate)
        ("monthly", 60, False, 3125),    # 1125 + 2000
        ("yearly", 60, False, 10500),    # 9000 + 2000 - 500
        ("monthly", 20, True, 3350),     # 1350 + 2000
        ("yearly", 20, True, 12300),     # 10800 + 2000 - 500
    ],
)
def test_membership_cost_with_personal_trainer(plan, age, is_student, expected):
    """Trainer adds 2000, with a 500 rebate for yearly subscribers."""
    assert membership_cost(plan, age, is_student, with_trainer=True) == expected


# ---------------------------------------------------------------------------
# Tests for can_enter function
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hour,gender", [(10, "M"), (10, "F"), (6, "M"), (20, "F")])
def test_can_enter_plan_inactive_denies_entry(hour, gender):
    """Inactive plan must deny gym entry immediately."""
    assert can_enter(hour, plan_active=False, is_women_only_slot=False, gender=gender) is False


@pytest.mark.parametrize("invalid_hour", [4, 3, 0, -1, 23, 24, 25])
def test_can_enter_outside_operational_hours_denies_entry(invalid_hour):
    """Hours strictly before 5 or strictly after 22 deny entry."""
    assert can_enter(invalid_hour, plan_active=True, is_women_only_slot=False, gender="M") is False


@pytest.mark.parametrize("valid_hour", [5, 6, 12, 18, 22])
def test_can_enter_during_operational_hours_permits_entry(valid_hour):
    """Hours between 5 and 22 inclusive permit entry for active plans."""
    assert can_enter(valid_hour, plan_active=True, is_women_only_slot=False, gender="M") is True


@pytest.mark.parametrize(
    "gender,expected",
    [
        ("F", True),
        ("M", False),
        ("Other", False),
        ("", False),
    ],
)
def test_can_enter_women_only_slot_access_control(gender, expected):
    """Women-only slot permits entry only if gender is 'F'."""
    assert can_enter(10, plan_active=True, is_women_only_slot=True, gender=gender) is expected


@pytest.mark.parametrize("gender", ["F", "M", "Other", "NB"])
def test_can_enter_standard_slot_permits_all_genders(gender):
    """Standard (non women-only) slot permits all genders."""
    assert can_enter(10, plan_active=True, is_women_only_slot=False, gender=gender) is True


# ---------------------------------------------------------------------------
# Tests for bmi_category function
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_height", [0, 0.0, -0.5, -1.8])
def test_bmi_category_non_positive_height_raises_error(invalid_height):
    """Height less than or equal to 0 must raise ValueError('invalid height')."""
    with pytest.raises(ValueError, match="invalid height"):
        bmi_category(70, invalid_height)


@pytest.mark.parametrize(
    "weight_kg,height_m",
    [
        (45.0, 1.70),  # BMI approx 15.57
        (18.4, 1.00),  # BMI 18.4 (< 18.5)
        (50.0, 1.80),  # BMI approx 15.43
    ],
)
def test_bmi_category_underweight(weight_kg, height_m):
    """BMI strictly below 18.5 is categorized as underweight."""
    assert bmi_category(weight_kg, height_m) == "underweight"


@pytest.mark.parametrize(
    "weight_kg,height_m",
    [
        (18.5, 1.00),  # BMI exactly 18.5 (lower normal boundary)
        (22.0, 1.00),  # Mid normal
        (65.0, 1.70),  # BMI approx 22.49
        (24.9, 1.00),  # BMI 24.9 (< 25)
    ],
)
def test_bmi_category_normal(weight_kg, height_m):
    """BMI in [18.5, 25.0) is categorized as normal."""
    assert bmi_category(weight_kg, height_m) == "normal"


@pytest.mark.parametrize(
    "weight_kg,height_m",
    [
        (25.0, 1.00),  # BMI exactly 25.0 (lower overweight boundary)
        (28.0, 1.00),  # Mid overweight
        (80.0, 1.75),  # BMI approx 26.12
        (29.9, 1.00),  # BMI 29.9 (< 30)
    ],
)
def test_bmi_category_overweight(weight_kg, height_m):
    """BMI in [25.0, 30.0) is categorized as overweight."""
    assert bmi_category(weight_kg, height_m) == "overweight"


@pytest.mark.parametrize(
    "weight_kg,height_m",
    [
        (30.0, 1.00),  # BMI exactly 30.0 (obese boundary)
        (35.0, 1.00),  # BMI 35.0
        (100.0, 1.75), # BMI approx 32.65
        (120.0, 1.70), # BMI approx 41.52
    ],
)
def test_bmi_category_obese(weight_kg, height_m):
    """BMI 30.0 and above is categorized as obese."""
    assert bmi_category(weight_kg, height_m) == "obese"
