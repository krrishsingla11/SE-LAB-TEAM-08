"""
Branch Coverage Test Suite for Gym Membership Application
Student: Kushal G
SRN: PES1UG24AM145
Scenario: Gym Membership
Application Module: gym_membership.py

This test suite specifically targets and verifies both True and False evaluation
branches for every conditional statement, compound predicate, and decision point
in gym_membership.py to achieve complete (100%) branch coverage.
"""

import pytest
from gym_membership import membership_cost, can_enter, bmi_category


# ===========================================================================
# Decision 1 & 2: Input validations in membership_cost
# ===========================================================================

def test_branch_membership_cost_plan_validation():
    """
    Decision 1: `if plan not in PLAN_PRICE:`
    - Branch True: invalid plan raises ValueError('unknown plan')
    - Branch False: valid plan proceeds to age validation
    """
    # Branch True:
    with pytest.raises(ValueError, match="unknown plan"):
        membership_cost("invalid_plan", 25, False, False)

    # Branch False (proceeds normally):
    cost = membership_cost("monthly", 25, False, False)
    assert cost == 1500


def test_branch_membership_cost_age_validation():
    """
    Decision 2: `if age < 14:`
    - Branch True: age < 14 raises ValueError('too young') (testing age=13 boundary)
    - Branch False: age >= 14 proceeds (testing age=14 boundary)
    """
    # Branch True (boundary: 13):
    with pytest.raises(ValueError, match="too young"):
        membership_cost("monthly", 13, False, False)

    # Branch False (boundary: 14):
    cost = membership_cost("monthly", 14, False, False)
    assert cost == 1500


# ===========================================================================
# Decision 3 & 4: Discount branching in membership_cost
# ===========================================================================

@pytest.mark.parametrize(
    "plan,age,is_student,with_trainer,expected_cost,description",
    [
        # Decision 3 - Branch True: age >= 60 (Senior discount 25% applied)
        ("monthly", 60, False, False, 1125, "Age 60 boundary: 1500 - 375 = 1125"),
        ("quarterly", 65, False, False, 3000, "Senior quarterly: 4000 - 1000 = 3000"),
        ("yearly", 70, False, False, 9000, "Senior yearly: 12000 - 3000 = 9000"),
        # Senior takes precedence when both age >= 60 and is_student are True
        ("monthly", 60, True, False, 1125, "Senior overrides student discount"),

        # Decision 3 - Branch False & Decision 4 - Branch True: age < 60 and is_student is True (10% off)
        ("monthly", 20, True, False, 1350, "Student monthly: 1500 - 150 = 1350"),
        ("quarterly", 25, True, False, 3600, "Student quarterly: 4000 - 400 = 3600"),
        ("yearly", 22, True, False, 10800, "Student yearly: 12000 - 1200 = 10800"),
        ("monthly", 59, True, False, 1350, "Student boundary age 59: 1500 - 150 = 1350"),

        # Decision 3 - Branch False & Decision 4 - Branch False: age < 60 and is_student is False
        ("monthly", 59, False, False, 1500, "Age 59 non-student: no discount"),
        ("quarterly", 30, False, False, 4000, "Adult quarterly non-student: no discount"),
        ("yearly", 30, False, False, 12000, "Adult yearly non-student: no discount"),
    ],
)
def test_branch_membership_cost_discount_paths(
    plan, age, is_student, with_trainer, expected_cost, description
):
    """Exercise senior, student, and non-discount branches in membership_cost."""
    assert membership_cost(plan, age, is_student, with_trainer) == expected_cost


# ===========================================================================
# Decision 5 & 6: Trainer add-on and yearly rebate branches
# ===========================================================================

@pytest.mark.parametrize(
    "plan,with_trainer,expected_cost,description",
    [
        # Decision 5 - Branch False: with_trainer is False
        ("monthly", False, 1500, "No trainer: cost unchanged"),
        ("yearly", False, 12000, "No trainer: cost unchanged"),

        # Decision 5 - Branch True: with_trainer is True
        # Decision 6 - Branch False: plan != 'yearly' (adds 2000, no rebate)
        ("monthly", True, 3500, "Monthly with trainer: 1500 + 2000 = 3500"),
        ("quarterly", True, 6000, "Quarterly with trainer: 4000 + 2000 = 6000"),

        # Decision 5 - Branch True & Decision 6 - Branch True: plan == 'yearly' (adds 2000, rebates 500)
        ("yearly", True, 13500, "Yearly with trainer: 12000 + 2000 - 500 = 13500"),
    ],
)
def test_branch_membership_cost_trainer_paths(plan, with_trainer, expected_cost, description):
    """Exercise trainer fee addition and yearly plan rebate branches."""
    assert membership_cost(plan, 30, is_student=False, with_trainer=with_trainer) == expected_cost


# ===========================================================================
# Decision 7, 8 & 9: Access control branches in can_enter
# ===========================================================================

def test_branch_can_enter_plan_active():
    """
    Decision 7: `if not plan_active:`
    - Branch True: plan_active is False -> returns False immediately
    - Branch False: plan_active is True -> proceeds to hour evaluation
    """
    # Branch True:
    assert can_enter(10, plan_active=False, is_women_only_slot=False, gender="M") is False
    # Branch False (proceeds):
    assert can_enter(10, plan_active=True, is_women_only_slot=False, gender="M") is True


def test_branch_can_enter_compound_hour_predicates():
    """
    Decision 8: `if hour < 5 or hour > 22:`
    In short-circuiting Boolean logic:
    - Path 8.1 (hour < 5 is True): hour=4 -> returns False immediately
    - Path 8.2 (hour < 5 is False, hour > 22 is True): hour=23 -> returns False
    - Path 8.3 (both False): hour=5 (lower bound) -> proceeds (returns True)
    - Path 8.4 (both False): hour=22 (upper bound) -> proceeds (returns True)
    - Path 8.5 (both False): hour=12 (midday) -> proceeds (returns True)
    """
    # Path 8.1: hour < 5 is True
    assert can_enter(4, plan_active=True, is_women_only_slot=False, gender="M") is False
    assert can_enter(0, plan_active=True, is_women_only_slot=False, gender="M") is False

    # Path 8.2: hour < 5 is False, hour > 22 is True
    assert can_enter(23, plan_active=True, is_women_only_slot=False, gender="M") is False
    assert can_enter(24, plan_active=True, is_women_only_slot=False, gender="M") is False

    # Path 8.3 & 8.4 & 8.5: both conditions False (valid hours)
    assert can_enter(5, plan_active=True, is_women_only_slot=False, gender="M") is True
    assert can_enter(22, plan_active=True, is_women_only_slot=False, gender="M") is True
    assert can_enter(12, plan_active=True, is_women_only_slot=False, gender="M") is True


def test_branch_can_enter_women_only_slot_and_default():
    """
    Decision 9: `if is_women_only_slot:`
    - Branch True: evaluates `return gender == 'F'`
        - gender == 'F' (True) -> returns True
        - gender == 'M' (False) -> returns False
        - gender == 'Other' (False) -> returns False
    - Branch False: falls through to `return True`
    """
    # Branch True, gender == 'F':
    assert can_enter(10, plan_active=True, is_women_only_slot=True, gender="F") is True

    # Branch True, gender != 'F':
    assert can_enter(10, plan_active=True, is_women_only_slot=True, gender="M") is False
    assert can_enter(10, plan_active=True, is_women_only_slot=True, gender="Other") is False

    # Branch False (standard slot): falls through to return True
    assert can_enter(10, plan_active=True, is_women_only_slot=False, gender="M") is True
    assert can_enter(10, plan_active=True, is_women_only_slot=False, gender="F") is True


# ===========================================================================
# Decision 10, 11, 12, 13: BMI category branching
# ===========================================================================

def test_branch_bmi_category_height_validation():
    """
    Decision 10: `if height_m <= 0:`
    - Branch True: height <= 0 raises ValueError('invalid height')
    - Branch False: height > 0 proceeds to BMI computation
    """
    # Branch True (boundary 0):
    with pytest.raises(ValueError, match="invalid height"):
        bmi_category(70, 0)

    # Branch True (negative):
    with pytest.raises(ValueError, match="invalid height"):
        bmi_category(70, -1.75)

    # Branch False (height > 0 proceeds normally):
    result = bmi_category(70, 1.75)
    assert result == "normal"


@pytest.mark.parametrize(
    "weight_kg,height_m,expected,description",
    [
        # Decision 11 - Branch True: bmi < 18.5
        (18.4, 1.0, "underweight", "BMI 18.4 < 18.5 (underweight branch True)"),
        (45.0, 1.7, "underweight", "BMI 15.57 < 18.5"),

        # Decision 11 - Branch False & Decision 12 - Branch True: 18.5 <= bmi < 25
        (18.5, 1.0, "normal", "BMI 18.5 exact lower bound for normal"),
        (22.0, 1.0, "normal", "BMI 22.0 mid-range normal"),
        (24.99, 1.0, "normal", "BMI 24.99 exact upper bound for normal"),

        # Decision 12 - Branch False & Decision 13 - Branch True: 25.0 <= bmi < 30
        (25.0, 1.0, "overweight", "BMI 25.0 exact lower bound for overweight"),
        (27.5, 1.0, "overweight", "BMI 27.5 mid-range overweight"),
        (29.99, 1.0, "overweight", "BMI 29.99 exact upper bound for overweight"),

        # Decision 13 - Branch False: bmi >= 30 (falls through to obese)
        (30.0, 1.0, "obese", "BMI 30.0 exact lower bound for obese"),
        (35.0, 1.0, "obese", "BMI 35.0 mid-range obese"),
        (120.0, 1.7, "obese", "BMI 41.52 high obese"),
    ],
)
def test_branch_bmi_category_classification_boundaries(
    weight_kg, height_m, expected, description
):
    """Exercise each branch of the BMI classification cascade at precise boundaries."""
    assert bmi_category(weight_kg, height_m) == expected
