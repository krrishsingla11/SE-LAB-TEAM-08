import pytest
from photo_print_order import extra_print_charge, order_valid, dispatch_status

# Example test cases:
def test_within_included_prints():
    assert extra_print_charge("4x6", 15, "matte", False) == 0

def test_order_valid():
    assert order_valid(10, 100, False) is True

# Write the rest of the test cases so that the code is 90-100% covered.
