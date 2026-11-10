"""
Code Coverage Test Suite for Photo Print Order Application
Student Name: Namith Kumar C
SRN: PES1UG24AM171
Course: Software Engineering Lab (UE24CS252AA)
Repository Scenario: L6_L7_46_photo_print_order
Application Module: photo_print_order.py

This test suite comprehensively exercises every executable statement and function
in photo_print_order.py to achieve complete code (line) coverage (>90%, target 100%).
"""

import pytest
from photo_print_order import (
    INCLUDED_PRINTS,
    extra_print_charge,
    order_valid,
    dispatch_status,
)


# ===========================================================================
# 1. Tests for INCLUDED_PRINTS dictionary configuration
# ===========================================================================

def test_included_prints_constants():
    """Verify standard included prints configuration mapping."""
    assert INCLUDED_PRINTS == {"4x6": 20, "5x7": 15, "8x10": 10}
    assert INCLUDED_PRINTS["4x6"] == 20
    assert INCLUDED_PRINTS["5x7"] == 15
    assert INCLUDED_PRINTS["8x10"] == 10


# ===========================================================================
# 2. Tests for extra_print_charge function
# ===========================================================================

@pytest.mark.parametrize("invalid_size", ["unknown", "2x3", "A4", "11x14", "", 123])
def test_extra_print_charge_unknown_size_raises(invalid_size):
    """Unknown or unsupported print size must raise ValueError('unknown print size')."""
    with pytest.raises(ValueError, match="unknown print size"):
        extra_print_charge(invalid_size, 10, "matte", False)


@pytest.mark.parametrize("negative_copies", [-1, -5, -100])
def test_extra_print_charge_negative_copies_raises(negative_copies):
    """Negative copies must raise ValueError('invalid copies')."""
    with pytest.raises(ValueError, match="invalid copies"):
        extra_print_charge("4x6", negative_copies, "matte", False)


@pytest.mark.parametrize(
    "print_size,copies,finish,is_member",
    [
        ("4x6", 0, "matte", False),       # 0 copies <= 20 included
        ("4x6", 20, "matte", False),      # exact included limit
        ("4x6", 15, "glossy", False),     # below included
        ("4x6", 25, "matte", True),       # member gets 20 + 5 = 25 included
        ("5x7", 15, "canvas", False),     # 5x7 exact included
        ("5x7", 20, "matte", True),       # 5x7 member gets 15 + 5 = 20 included
        ("8x10", 10, "matte", False),     # 8x10 exact included
        ("8x10", 10, "matte", True),      # 8x10 member does NOT get extra (included = 10)
    ],
)
def test_extra_print_charge_zero_when_within_included(print_size, copies, finish, is_member):
    """When copies <= included, extra print charge should be 0."""
    assert extra_print_charge(print_size, copies, finish, is_member) == 0


def test_extra_print_charge_member_8x10_not_incremented():
    """Member discount excludes 8x10 size (print_size == '8x10' condition)."""
    # 8x10 with 12 copies: included remains 10. extra = 2.
    # finish "matte" -> rate = 4 -> total = 2 * 4 = 8
    assert extra_print_charge("8x10", 12, "matte", True) == 8


def test_extra_print_charge_matte_normal_volume():
    """Matte finish with extra <= 50 prints charges rate of 4 per extra copy."""
    # 4x6 non-member: included = 20. copies = 30 -> extra = 10 (<= 50).
    # rate = 4. total = 10 * 4 = 40.
    assert extra_print_charge("4x6", 30, "matte", False) == 40


def test_extra_print_charge_non_matte_normal_volume():
    """Non-matte finish (glossy) with extra <= 50 prints charges rate of 7."""
    # 4x6 non-member: included = 20. copies = 30 -> extra = 10 (<= 50).
    # rate = 7. total = 10 * 7 = 70.
    assert extra_print_charge("4x6", 30, "glossy", False) == 70


def test_extra_print_charge_matte_high_volume():
    """Matte finish with extra > 50 prints charges rate of (4 + 2) = 6."""
    # 4x6 non-member: included = 20. copies = 71 -> extra = 51 (> 50).
    # finish "matte" != "canvas", rate = 4 + 2 = 6. total = 51 * 6 = 306.
    assert extra_print_charge("4x6", 71, "matte", False) == 306


def test_extra_print_charge_glossy_high_volume():
    """Glossy finish with extra > 50 prints charges rate of (7 + 2) = 9."""
    # 4x6 non-member: included = 20. copies = 80 -> extra = 60 (> 50).
    # finish "glossy" != "canvas", rate = 7 + 2 = 9. total = 60 * 9 = 540.
    assert extra_print_charge("4x6", 80, "glossy", False) == 540


def test_extra_print_charge_canvas_high_volume():
    """Canvas finish with extra > 50 prints charges rate of (7 + 2 + 5) = 14."""
    # 4x6 non-member: included = 20. copies = 71 -> extra = 51 (> 50).
    # finish == "canvas", rate = 7 + 2 + 5 = 14. total = 51 * 14 = 714.
    assert extra_print_charge("4x6", 71, "canvas", False) == 714


# ===========================================================================
# 3. Tests for order_valid function
# ===========================================================================

@pytest.mark.parametrize(
    "copies,expected",
    [
        (50, True),   # boundary: exactly 50 copies in rush
        (30, True),   # within rush limit
        (0, True),    # minimum copies
        (51, False),  # boundary: exceeds 50 copies in rush
        (100, False), # well over rush limit
    ],
)
def test_order_valid_rush_orders(copies, expected):
    """Rush orders accept maximum 50 copies regardless of file size."""
    assert order_valid(file_mb=50, copies=copies, is_rush=True) is expected


def test_order_valid_non_rush_oversized_file():
    """Non-rush orders reject files larger than 25 MB."""
    # file_mb = 26 (> 25) -> False immediately
    assert order_valid(file_mb=26, copies=10, is_rush=False) is False
    assert order_valid(file_mb=100, copies=1, is_rush=False) is False


@pytest.mark.parametrize(
    "file_mb,copies,expected",
    [
        (25, 500, True),   # exact boundary: 25 MB and 500 copies
        (10, 200, True),   # standard valid order
        (1, 1, True),      # small order
        (25, 501, False),  # copies exceed 500 boundary
        (10, 600, False),  # copies exceed 500
    ],
)
def test_order_valid_non_rush_standard_file(file_mb, copies, expected):
    """Non-rush orders with file <= 25 MB allow up to 500 copies."""
    assert order_valid(file_mb, copies, is_rush=False) is expected


# ===========================================================================
# 4. Tests for dispatch_status function
# ===========================================================================

@pytest.mark.parametrize(
    "hours,is_framed,is_international,expected",
    [
        # Unframed, Domestic: cutoff = 12
        (15, False, False, "on_time"),  # > 12
        (12, False, False, "on_time"),  # exact cutoff 12
        (11, False, False, "tight"),    # cutoff - 1
        (6, False, False, "tight"),     # cutoff - 6 (boundary)
        (5, False, False, "missed"),    # cutoff - 7
        (0, False, False, "missed"),    # 0 hours left

        # Framed, Domestic: cutoff = 24
        (30, True, False, "on_time"),   # > 24
        (24, True, False, "on_time"),   # exact cutoff 24
        (23, True, False, "tight"),     # cutoff - 1
        (18, True, False, "tight"),     # cutoff - 6 (boundary)
        (17, True, False, "missed"),    # cutoff - 7
        (0, True, False, "missed"),

        # Unframed, International: cutoff = 12 + 24 = 36
        (40, False, True, "on_time"),   # > 36
        (36, False, True, "on_time"),   # exact cutoff 36
        (35, False, True, "tight"),     # cutoff - 1
        (30, False, True, "tight"),     # cutoff - 6 (boundary)
        (29, False, True, "missed"),    # cutoff - 7

        # Framed, International: cutoff = 24 + 24 = 48
        (50, True, True, "on_time"),    # > 48
        (48, True, True, "on_time"),    # exact cutoff 48
        (47, True, True, "tight"),      # cutoff - 1
        (42, True, True, "tight"),      # cutoff - 6 (boundary)
        (41, True, True, "missed"),     # cutoff - 7
    ],
)
def test_dispatch_status_scenarios(hours, is_framed, is_international, expected):
    """Verify dispatch status thresholds across framing and international shipping."""
    assert dispatch_status(hours, is_framed, is_international) == expected
