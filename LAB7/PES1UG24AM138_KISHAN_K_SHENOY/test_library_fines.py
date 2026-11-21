"""Hypothesis Fuzz Testing and Property-Based Verification for Library Fines.

Student: Kishan K Shenoy
SRN: PES1UG24AM138
Scenario: 14 — Library Fines
Target Module: library_fines.py
"""

import pytest
from hypothesis import given, strategies as st

from library_fines import parse_member_id, total_fine, shelf_code

ALLOWED_EXCEPTIONS = (ValueError, TypeError)

UNEXPECTED_INPUTS = st.one_of(
    st.text(),
    st.none(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.booleans(),
    st.lists(st.text(), max_size=3),
)


# ===========================================================================
# A. Fuzz / Robustness Tests (No Unexpected Crashes)
# ===========================================================================

@given(
    st.one_of(
        UNEXPECTED_INPUTS,
        st.builds(
            lambda t, n: f"{t}-{n}",
            st.text(),
            st.integers(),
        ),
    )
)
def test_parse_member_id_no_crash(s):
    """Fuzz test: parse_member_id must never crash unexpectedly on arbitrary input."""
    try:
        result = parse_member_id(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(result, tuple)
    assert len(result) == 2
    member_type, number = result
    assert isinstance(member_type, str)
    assert len(member_type) > 0
    assert member_type == member_type.upper()
    assert isinstance(number, int) and not isinstance(number, bool)
    assert number >= 0


@given(
    st.one_of(
        UNEXPECTED_INPUTS,
        st.builds(
            lambda nums: ",".join(str(n) for n in nums),
            st.lists(st.integers(min_value=-1000, max_value=10000), max_size=10),
        ),
    )
)
def test_total_fine_no_crash(s):
    """Fuzz test: total_fine must never crash unexpectedly on arbitrary input."""
    try:
        fine = total_fine(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(fine, int) and not isinstance(fine, bool)
    assert fine >= 0


@given(UNEXPECTED_INPUTS)
def test_shelf_code_no_crash(s):
    """Fuzz test: shelf_code must never crash unexpectedly on arbitrary input."""
    try:
        code = shelf_code(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(code, str)
    assert len(code) >= 2
    assert code == code.upper()


# ===========================================================================
# B. Property-Based Tests
# ===========================================================================

# 1. Properties of parse_member_id
valid_types = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
    min_size=1,
    max_size=20,
).filter(lambda t: t.strip() != "")


@given(mtype=valid_types, num=st.integers(min_value=0, max_value=10**9))
def test_parse_member_id_valid_properties(mtype, num):
    """Valid 'type-number' input must return uppercase type and correct integer."""
    raw = f"{mtype}-{num}"
    parsed_type, parsed_num = parse_member_id(raw)

    assert parsed_type == mtype.strip().upper()
    assert parsed_type == parsed_type.upper()
    assert len(parsed_type) > 0
    assert isinstance(parsed_num, int) and not isinstance(parsed_num, bool)
    assert parsed_num == num


@given(mtype=valid_types, num=st.integers(min_value=-10**6, max_value=-1))
def test_parse_member_id_rejects_negative_number(mtype, num):
    """Negative member number must raise ValueError."""
    with pytest.raises(ValueError):
        parse_member_id(f"{mtype}-{num}")


@given(
    blank=st.text(alphabet=" \t\r\n", min_size=0, max_size=10),
    num=st.integers(min_value=0, max_value=1000),
)
def test_parse_member_id_rejects_empty_type(blank, num):
    """Empty or whitespace-only member type must raise ValueError."""
    with pytest.raises(ValueError):
        parse_member_id(f"{blank}-{num}")


# 2. Properties of total_fine
@given(days=st.lists(st.integers(min_value=0, max_value=14), min_size=1, max_size=30))
def test_total_fine_on_time_zero_fine(days):
    """Days <= 14 must always incur zero fine."""
    csv_str = ",".join(str(d) for d in days)
    assert total_fine(csv_str) == 0


@given(days=st.lists(st.integers(min_value=0, max_value=365), min_size=1, max_size=30))
def test_total_fine_matches_formula(days):
    """Total fine must exactly equal sum(max(0, (d - 14) * 2))."""
    csv_str = ",".join(str(d) for d in days)
    expected = sum((d - 14) * 2 for d in days if d > 14)
    assert total_fine(csv_str) == expected


@given(
    d1=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=10),
    d2=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=10),
)
def test_total_fine_additivity(d1, d2):
    """total_fine(d1 + d2) == total_fine(d1) + total_fine(d2)."""
    csv1 = ",".join(str(x) for x in d1)
    csv2 = ",".join(str(x) for x in d2)
    csv_combined = f"{csv1},{csv2}"
    assert total_fine(csv_combined) == total_fine(csv1) + total_fine(csv2)


@given(whitespace=st.text(alphabet=" \t\r\n", min_size=0, max_size=10))
def test_total_fine_rejects_empty_input(whitespace):
    """Empty CSV string must raise ValueError."""
    with pytest.raises(ValueError):
        total_fine(whitespace)


@given(
    prefix=st.lists(st.integers(min_value=0, max_value=100), max_size=5),
    neg=st.integers(min_value=-1000, max_value=-1),
    suffix=st.lists(st.integers(min_value=0, max_value=100), max_size=5),
)
def test_total_fine_rejects_negative_days(prefix, neg, suffix):
    """Negative day values must raise ValueError."""
    raw = ",".join(str(x) for x in [*prefix, neg, *suffix])
    with pytest.raises(ValueError):
        total_fine(raw)


# 3. Properties of shelf_code
ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
valid_words = st.text(alphabet=ascii_letters, min_size=1, max_size=15)


@given(w1=valid_words, w2=valid_words)
def test_shelf_code_two_words_properties(w1, w2):
    """Two valid words produce two-character uppercase code of their initials."""
    title = f"{w1} {w2}"
    code = shelf_code(title)
    assert len(code) == 2
    assert code == (w1[0] + w2[0]).upper()


@given(w1=valid_words, w2=valid_words, extra=st.lists(valid_words, min_size=1, max_size=5))
def test_shelf_code_multiple_words_uses_first_two(w1, w2, extra):
    """Titles with > 2 words only use the first two words for shelf code."""
    title = f"{w1} {w2} " + " ".join(extra)
    code = shelf_code(title)
    assert code == (w1[0] + w2[0]).upper()


@given(single_word=valid_words)
def test_shelf_code_rejects_single_word(single_word):
    """Single-word title must raise ValueError."""
    with pytest.raises(ValueError):
        shelf_code(single_word)


@given(whitespace=st.text(alphabet=" \t\r\n", min_size=0, max_size=10))
def test_shelf_code_rejects_empty(whitespace):
    """Empty or whitespace-only title must raise ValueError."""
    with pytest.raises(ValueError):
        shelf_code(whitespace)
