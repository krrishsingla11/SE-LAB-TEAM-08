"""
Branch Coverage Test Suite for Photo Print Order Application
Student Name: Namith Kumar C
SRN: PES1UG24AM171
Course: Software Engineering Lab (UE24CS252AA)
Repository Scenario: L6_L7_46_photo_print_order
Application Module: photo_print_order.py

This test suite specifically targets and verifies every True and False conditional
evaluation branch, decision point, and compound predicate in photo_print_order.py
to achieve 100% branch coverage.
"""

import pytest
from photo_print_order import (
    extra_print_charge,
    order_valid,
    dispatch_status,
)


# ===========================================================================
# Decision 1: `if print_size not in INCLUDED_PRINTS:`
# ===========================================================================

def test_branch_print_size_validation():
    """
    Decision 1: `if print_size not in INCLUDED_PRINTS:`
    - True Branch: invalid print_size raises ValueError('unknown print size')
    - False Branch: valid print_size proceeds to copies validation
    """
    # True branch:
    with pytest.raises(ValueError, match="unknown print size"):
        extra_print_charge("poster_size", 10, "matte", False)

    # False branch:
    charge = extra_print_charge("4x6", 20, "matte", False)
    assert charge == 0


# ===========================================================================
# Decision 2: `if copies < 0:`
# ===========================================================================

def test_branch_copies_negative_validation():
    """
    Decision 2: `if copies < 0:`
    - True Branch: copies < 0 raises ValueError('invalid copies') (boundary: copies = -1)
    - False Branch: copies >= 0 proceeds (boundary: copies = 0)
    """
    # True branch:
    with pytest.raises(ValueError, match="invalid copies"):
        extra_print_charge("4x6", -1, "matte", False)

    # False branch:
    charge = extra_print_charge("4x6", 0, "matte", False)
    assert charge == 0


# ===========================================================================
# Decision 3: Compound predicate `if is_member and print_size != "8x10":`
# ===========================================================================

def test_branch_member_discount_compound_predicate():
    """
    Decision 3: `if is_member and print_size != '8x10':`
    - Branch 3A (True AND True -> True): member=True with '4x6' -> included becomes 25
    - Branch 3B (False -> short-circuits to False): member=False with '4x6' -> included remains 20
    - Branch 3C (True AND False -> False): member=True with '8x10' -> included remains 10
    """
    # 3A: True AND True -> True
    # 4x6 member has 25 included. 25 copies -> extra = 0 -> charge = 0.
    # 26 copies -> extra = 1 * 4 = 4.
    assert extra_print_charge("4x6", 26, "matte", is_member=True) == 4

    # 3B: is_member=False -> False
    # 4x6 non-member has 20 included. 26 copies -> extra = 6 * 4 = 24.
    assert extra_print_charge("4x6", 26, "matte", is_member=False) == 24

    # 3C: True AND False ('8x10') -> False
    # 8x10 member has 10 included (no bonus). 12 copies -> extra = 2 * 4 = 8.
    assert extra_print_charge("8x10", 12, "matte", is_member=True) == 8


# ===========================================================================
# Decision 4: `if extra <= 0:`
# ===========================================================================

def test_branch_extra_copies_boundary():
    """
    Decision 4: `if extra <= 0:`
    - True Branch: extra <= 0 (e.g. copies == included or copies < included) -> returns 0
    - False Branch: extra > 0 -> proceeds to calculate finish rates
    """
    # True branch: copies = 20 on 4x6 (extra = 0)
    assert extra_print_charge("4x6", 20, "matte", False) == 0

    # True branch: copies = 10 on 4x6 (extra = -10 < 0)
    assert extra_print_charge("4x6", 10, "matte", False) == 0

    # False branch: copies = 21 on 4x6 (extra = 1 > 0)
    assert extra_print_charge("4x6", 21, "matte", False) == 4


# ===========================================================================
# Decision 5: `if finish == "matte":`
# ===========================================================================

def test_branch_finish_type_selection():
    """
    Decision 5: `if finish == 'matte':`
    - True Branch: finish is 'matte' -> base rate = 4
    - False Branch: finish is other (e.g. 'glossy') -> base rate = 7
    """
    # True branch: matte, extra = 10 -> 10 * 4 = 40
    assert extra_print_charge("4x6", 30, "matte", False) == 40

    # False branch: glossy, extra = 10 -> 10 * 7 = 70
    assert extra_print_charge("4x6", 30, "glossy", False) == 70


# ===========================================================================
# Decision 6 & 7: `if extra > 50:` and nested `if finish == "canvas":`
# ===========================================================================

def test_branch_high_volume_and_canvas_surcharges():
    """
    Decision 6: `if extra > 50:`
    - False Branch: extra <= 50 (boundary: extra = 50) -> no volume surcharge
    - True Branch: extra > 50 (boundary: extra = 51) -> rate += 2

    Decision 7: `if finish == 'canvas':` (nested inside extra > 50)
    - False Branch: finish is not canvas (e.g. 'matte' or 'glossy') -> no canvas surcharge
    - True Branch: finish is 'canvas' -> rate += 5
    """
    # Decision 6 False branch: boundary extra = 50 (70 copies - 20 included)
    # finish = 'matte' -> rate = 4 -> total = 50 * 4 = 200
    assert extra_print_charge("4x6", 70, "matte", False) == 200

    # Decision 6 False branch with glossy: extra = 50
    # finish = 'glossy' -> rate = 7 -> total = 50 * 7 = 350
    assert extra_print_charge("4x6", 70, "glossy", False) == 350

    # Decision 6 True branch + Decision 7 False branch (matte):
    # extra = 51 (71 copies). rate = 4 + 2 = 6 -> total = 51 * 6 = 306
    assert extra_print_charge("4x6", 71, "matte", False) == 306

    # Decision 6 True branch + Decision 7 False branch (glossy):
    # extra = 51 (71 copies). rate = 7 + 2 = 9 -> total = 51 * 9 = 459
    assert extra_print_charge("4x6", 71, "glossy", False) == 459

    # Decision 6 True branch + Decision 7 True branch (canvas):
    # extra = 51 (71 copies). rate = 7 + 2 + 5 = 14 -> total = 51 * 14 = 714
    assert extra_print_charge("4x6", 71, "canvas", False) == 714


# ===========================================================================
# Decision 8: `if is_rush:` in order_valid
# ===========================================================================

def test_branch_order_valid_is_rush():
    """
    Decision 8: `if is_rush:`
    - True Branch: returns copies <= 50
        - subcase copies <= 50 -> True (boundary: 50)
        - subcase copies > 50 -> False (boundary: 51)
    - False Branch: proceeds to file_mb check
    """
    # True branch, copies <= 50
    assert order_valid(file_mb=10, copies=50, is_rush=True) is True

    # True branch, copies > 50
    assert order_valid(file_mb=10, copies=51, is_rush=True) is False

    # False branch (is_rush=False proceeds to standard order checks)
    assert order_valid(file_mb=10, copies=100, is_rush=False) is True


# ===========================================================================
# Decision 9 & 10: `if file_mb > 25:` and `return copies <= 500`
# ===========================================================================

def test_branch_order_valid_file_size_and_copies():
    """
    Decision 9: `if file_mb > 25:`
    - True Branch: file_mb > 25 -> returns False immediately (boundary: 26)
    - False Branch: file_mb <= 25 -> proceeds to copies <= 500 check (boundary: 25)

    Decision 10: `return copies <= 500`
    - Outcome True: copies <= 500 (boundary: 500)
    - Outcome False: copies > 500 (boundary: 501)
    """
    # Decision 9 True branch: file_mb = 26 > 25
    assert order_valid(file_mb=26, copies=10, is_rush=False) is False

    # Decision 9 False branch + Decision 10 True outcome:
    # file_mb = 25 <= 25, copies = 500 <= 500
    assert order_valid(file_mb=25, copies=500, is_rush=False) is True

    # Decision 9 False branch + Decision 10 False outcome:
    # file_mb = 25 <= 25, copies = 501 > 500
    assert order_valid(file_mb=25, copies=501, is_rush=False) is False


# ===========================================================================
# Decision 11 & 12: `if is_framed:` and `if is_international:` in dispatch_status
# ===========================================================================

def test_branch_dispatch_cutoff_determination():
    """
    Decision 11: `if is_framed:`
    - True Branch: cutoff = 24
    - False Branch: cutoff = 12

    Decision 12: `if is_international:`
    - True Branch: cutoff += 24
    - False Branch: cutoff unchanged
    """
    # Framing False (12), International False (0) -> cutoff = 12
    assert dispatch_status(12, is_framed=False, is_international=False) == "on_time"

    # Framing True (24), International False (0) -> cutoff = 24
    assert dispatch_status(24, is_framed=True, is_international=False) == "on_time"

    # Framing False (12), International True (+24) -> cutoff = 36
    assert dispatch_status(36, is_framed=False, is_international=True) == "on_time"

    # Framing True (24), International True (+24) -> cutoff = 48
    assert dispatch_status(48, is_framed=True, is_international=True) == "on_time"


# ===========================================================================
# Decision 13 & 14: `if hours >= cutoff:` and `elif hours >= cutoff - 6:`
# ===========================================================================

def test_branch_dispatch_time_status_evaluation():
    """
    Decision 13: `if hours_before_dispatch >= cutoff:`
    - True Branch: returns 'on_time'
    - False Branch: proceeds to elif

    Decision 14: `elif hours_before_dispatch >= cutoff - 6:`
    - True Branch: returns 'tight' (boundary: cutoff - 6)
    - False Branch: returns 'missed' (boundary: cutoff - 7)
    """
    # Cutoff = 12 (unframed, domestic)
    # Decision 13 True: hours = 12 >= 12 -> 'on_time'
    assert dispatch_status(12, False, False) == "on_time"

    # Decision 13 False, Decision 14 True: hours = 11 (cutoff - 1) -> 'tight'
    assert dispatch_status(11, False, False) == "tight"

    # Decision 13 False, Decision 14 True: hours = 6 (exact cutoff - 6 boundary) -> 'tight'
    assert dispatch_status(6, False, False) == "tight"

    # Decision 13 False, Decision 14 False: hours = 5 (cutoff - 7) -> 'missed'
    assert dispatch_status(5, False, False) == "missed"

    # Decision 13 False, Decision 14 False: hours = 0 -> 'missed'
    assert dispatch_status(0, False, False) == "missed"
