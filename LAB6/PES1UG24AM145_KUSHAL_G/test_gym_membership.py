import pytest
from gym_membership import membership_cost, can_enter, bmi_category

#Example test cases:
def test_monthly_plan():
    assert membership_cost("monthly", 30, False, False) == 1500

def test_can_enter():
    assert can_enter(10, True, False, "M") is True

#Write the rest of the test cases so that the code is 90- 100% covered.
