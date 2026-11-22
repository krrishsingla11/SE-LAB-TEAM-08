import pytest
from library_fines import late_fine, can_borrow, renewal_status

# Example test cases:
def test_returned_on_time():
    assert late_fine("student", 10, False) == 0

def test_can_borrow():
    assert can_borrow(1, 0, "student") is True

# Additional test cases to achieve 90-100% coverage
def test_unknown_member():
    with pytest.raises(ValueError, match="unknown member"):
        late_fine("alumni", 5, False)

def test_negative_days():
    with pytest.raises(ValueError, match="invalid days"):
        late_fine("student", -1, False)

def test_faculty_late_with_cap_and_damage():
    # 30 loan days, kept 300 days -> overdue 270 * 1 = 270 -> capped at 200 + 150 damage = 350
    assert late_fine("faculty", 300, True) == 350

def test_guest_late_without_cap():
    # 14 loan days, kept 20 days -> overdue 6 * 5 = 30 + 0 = 30
    assert late_fine("guest", 20, False) == 30

def test_can_borrow_pending_fine():
    assert can_borrow(0, 150, "student") is False

def test_can_borrow_faculty_limit():
    assert can_borrow(9, 50, "faculty") is True
    assert can_borrow(10, 50, "faculty") is False

def test_can_borrow_student_limit():
    assert can_borrow(2, 50, "student") is True
    assert can_borrow(3, 50, "student") is False

def test_renewal_reservation():
    assert renewal_status(0, True, 5) == "denied"

def test_renewal_limit_reached():
    assert renewal_status(2, False, 5) == "limit reached"

def test_renewal_overdue():
    assert renewal_status(1, False, -1) == "overdue"

def test_renewal_successful():
    assert renewal_status(1, False, 5) == "renewed"
