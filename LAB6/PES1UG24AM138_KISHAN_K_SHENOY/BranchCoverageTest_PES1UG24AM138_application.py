"""Branch Coverage Test Suite for Library Fines Application.

Student: Kishan K Shenoy
SRN: PES1UG24AM138
Scenario: 14 — Library Fines
Target Module: library_fines.py

Specifically exercises every True and False conditional branch across all functions.
"""

import pytest
from library_fines import late_fine, can_borrow, renewal_status


def test_branch_member_validity():
    """Branch 1: member not in DAILY_FINE (True vs False)."""
    # True branch -> raise ValueError
    with pytest.raises(ValueError, match="unknown member"):
        late_fine("visitor", 10, False)

    # False branch -> proceed
    assert late_fine("student", 10, False) == 0


def test_branch_days_kept_validity():
    """Branch 2: days_kept < 0 (True vs False)."""
    # True branch -> raise ValueError
    with pytest.raises(ValueError, match="invalid days"):
        late_fine("student", -1, False)

    # False branch (boundary 0) -> proceed
    assert late_fine("student", 0, False) == 0


def test_branch_late_fine_member_type():
    """Branch 3: member == 'faculty' loan days (30 vs 14)."""
    # True branch: loan_days = 30
    assert late_fine("faculty", 30, False) == 0
    assert late_fine("faculty", 31, False) == 1

    # False branch: loan_days = 14
    assert late_fine("student", 14, False) == 0
    assert late_fine("student", 15, False) == 2


def test_branch_overdue_condition():
    """Branch 4: overdue > 0 (True vs False)."""
    # False branch (on-time or early) -> fine = 0
    assert late_fine("student", 12, False) == 0
    assert late_fine("student", 14, False) == 0

    # True branch (overdue) -> fine calculated
    assert late_fine("student", 16, False) == 4


def test_branch_fine_cap():
    """Branch 5: fine > 200 (True vs False)."""
    # False branch: fine <= 200 remains uncapped
    # 100 days overdue * 2 = 200 (exact boundary)
    assert late_fine("student", 114, False) == 200

    # True branch: fine > 200 clamped to 200
    # 101 days overdue * 2 = 202 -> capped to 200
    assert late_fine("student", 115, False) == 200


def test_branch_damage_fee():
    """Branch 6: is_damaged (True vs False)."""
    # False branch: no extra damage fee
    assert late_fine("student", 10, False) == 0

    # True branch: adds 150 damage fee
    assert late_fine("student", 10, True) == 150


def test_branch_can_borrow_pending_fine():
    """Branch 7: pending_fine > 100 (True vs False)."""
    # True branch: rejected immediately
    assert can_borrow(0, 100.01, "student") is False
    assert can_borrow(0, 150, "faculty") is False

    # False branch: boundary 100 passes fine check
    assert can_borrow(0, 100, "student") is True


def test_branch_can_borrow_member_limits():
    """Branches 8, 9, 10: member == 'faculty' (books_held < 10 vs books_held < 3)."""
    # Faculty True branch, books_held < 10 True
    assert can_borrow(9, 0, "faculty") is True
    # Faculty True branch, books_held < 10 False
    assert can_borrow(10, 0, "faculty") is False

    # Faculty False branch (e.g. student/guest), books_held < 3 True
    assert can_borrow(2, 0, "student") is True
    # Faculty False branch (e.g. student/guest), books_held < 3 False
    assert can_borrow(3, 0, "student") is False


def test_branch_renewal_has_reservation():
    """Branch 11: has_reservation (True vs False)."""
    # True branch -> 'denied'
    assert renewal_status(0, True, 10) == "denied"

    # False branch -> continue evaluation
    assert renewal_status(0, False, 10) == "renewed"


def test_branch_renewal_limit_and_overdue():
    """Branches 12 & 13: times_renewed >= 2 (True/False) & days_left < 0 (True/False)."""
    # times_renewed >= 2 True -> 'limit reached'
    assert renewal_status(2, False, 10) == "limit reached"
    assert renewal_status(3, False, -5) == "limit reached"

    # times_renewed >= 2 False AND days_left < 0 True -> 'overdue'
    assert renewal_status(1, False, -1) == "overdue"

    # times_renewed >= 2 False AND days_left < 0 False -> 'renewed'
    assert renewal_status(1, False, 0) == "renewed"
    assert renewal_status(0, False, 5) == "renewed"
