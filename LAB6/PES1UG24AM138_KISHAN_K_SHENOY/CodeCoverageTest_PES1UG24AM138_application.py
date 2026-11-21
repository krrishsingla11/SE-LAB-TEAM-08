"""Code Coverage Test Suite for Library Fines Application.

Student: Kishan K Shenoy
SRN: PES1UG24AM138
Scenario: 14 — Library Fines
Target Module: library_fines.py
"""

import pytest
from library_fines import DAILY_FINE, late_fine, can_borrow, renewal_status


class TestCodeCoverageConstants:
    """Validate module-level constants and definitions."""

    def test_daily_fine_dictionary(self):
        assert DAILY_FINE["student"] == 2
        assert DAILY_FINE["faculty"] == 1
        assert DAILY_FINE["guest"] == 5


class TestCodeCoverageLateFine:
    """Test statement coverage for late_fine function."""

    def test_unknown_member_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown member"):
            late_fine("alumni", 10, False)

    def test_negative_days_raises_value_error(self):
        with pytest.raises(ValueError, match="invalid days"):
            late_fine("student", -5, False)

    def test_faculty_on_time_no_damage(self):
        assert late_fine("faculty", 30, False) == 0

    def test_faculty_overdue_uncapped_no_damage(self):
        # 30 loan days, kept 40 days -> overdue 10 * 1 = 10
        assert late_fine("faculty", 40, False) == 10

    def test_faculty_overdue_capped_with_damage(self):
        # overdue 250 * 1 = 250 -> capped at 200 + 150 = 350
        assert late_fine("faculty", 280, True) == 350

    def test_student_on_time_with_damage(self):
        # 14 loan days, kept 14 -> overdue 0, fine 0 + 150 = 150
        assert late_fine("student", 14, True) == 150

    def test_student_overdue_uncapped_no_damage(self):
        # 14 loan days, kept 20 -> overdue 6 * 2 = 12
        assert late_fine("student", 20, False) == 12

    def test_student_overdue_capped_without_damage(self):
        # overdue 105 * 2 = 210 -> capped at 200
        assert late_fine("student", 119, False) == 200

    def test_guest_on_time_no_damage(self):
        assert late_fine("guest", 10, False) == 0

    def test_guest_overdue_uncapped_with_damage(self):
        # overdue 5 * 5 = 25 + 150 = 175
        assert late_fine("guest", 19, True) == 175

    def test_guest_overdue_capped_with_damage(self):
        # overdue 50 * 5 = 250 -> capped at 200 + 150 = 350
        assert late_fine("guest", 64, True) == 350


class TestCodeCoverageCanBorrow:
    """Test statement coverage for can_borrow function."""

    def test_pending_fine_over_100_rejected(self):
        assert can_borrow(0, 101, "faculty") is False
        assert can_borrow(1, 150, "student") is False

    def test_pending_fine_exactly_100_allowed(self):
        assert can_borrow(5, 100, "faculty") is True

    def test_faculty_under_limit(self):
        assert can_borrow(9, 50, "faculty") is True

    def test_faculty_at_or_above_limit(self):
        assert can_borrow(10, 50, "faculty") is False
        assert can_borrow(12, 0, "faculty") is False

    def test_student_under_limit(self):
        assert can_borrow(2, 50, "student") is True

    def test_student_at_or_above_limit(self):
        assert can_borrow(3, 50, "student") is False
        assert can_borrow(5, 0, "student") is False

    def test_guest_under_limit(self):
        assert can_borrow(2, 20, "guest") is True

    def test_guest_at_or_above_limit(self):
        assert can_borrow(3, 20, "guest") is False


class TestCodeCoverageRenewalStatus:
    """Test statement coverage for renewal_status function."""

    def test_reservation_denied(self):
        assert renewal_status(0, True, 5) == "denied"
        assert renewal_status(2, True, -2) == "denied"

    def test_limit_reached(self):
        assert renewal_status(2, False, 5) == "limit reached"
        assert renewal_status(3, False, 10) == "limit reached"

    def test_overdue_when_negative_days(self):
        assert renewal_status(0, False, -1) == "overdue"
        assert renewal_status(1, False, -10) == "overdue"

    def test_renewed_when_eligible(self):
        assert renewal_status(0, False, 0) == "renewed"
        assert renewal_status(1, False, 7) == "renewed"
