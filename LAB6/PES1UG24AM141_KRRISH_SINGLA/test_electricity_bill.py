import pytest
from electricity_bill import energy_charge, late_fee, subsidy

#Example test cases:
def test_low_usage_domestic():
    assert energy_charge(50, "domestic") == 200

def test_paid_on_time():
    assert late_fee(500, 0) == 0

#Write the rest of the test cases so that the code is 90- 100% covered.
