import math
import pytest
from hypothesis import given, strategies as st

from photo_print_order import parse_order, file_size_average, payable_amount

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
            lambda s, c: f"{s}:{c}",
            st.text(),
            st.integers(),
        ),
    )
)
def test_parse_order_no_crash(s):
    """Fuzz test: parse_order must never crash unexpectedly on arbitrary input."""
    try:
        result = parse_order(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(result, tuple)
    assert len(result) == 2
    size, copies = result
    assert isinstance(size, str)
    assert len(size) > 0
    assert size == size.upper()
    assert isinstance(copies, int) and not isinstance(copies, bool)
    assert copies > 0


@given(
    st.one_of(
        UNEXPECTED_INPUTS,
        st.builds(
            lambda nums: ",".join(str(n) for n in nums),
            st.lists(st.integers(min_value=-1000, max_value=10000), max_size=10),
        ),
    )
)
def test_file_size_average_no_crash(s):
    """Fuzz test: file_size_average must never crash unexpectedly on arbitrary input."""
    try:
        avg = file_size_average(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(avg, int) and not isinstance(avg, bool)
    assert avg >= 0


@given(
    st.one_of(
        UNEXPECTED_INPUTS,
        st.builds(
            lambda a, d: f"{a}|{d}",
            st.floats(allow_nan=True, allow_infinity=True),
            st.floats(allow_nan=True, allow_infinity=True),
        ),
    )
)
def test_payable_amount_no_crash(s):
    """Fuzz test: payable_amount must never crash unexpectedly on arbitrary input."""
    try:
        total = payable_amount(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(total, float)
    assert math.isfinite(total)
    assert total >= 0.0
    assert total == round(total, 2)


# ===========================================================================
# B. Property-Based Tests
# ===========================================================================

# 1. Properties of parse_order
valid_sizes = st.text(
    alphabet=st.characters(blacklist_characters=":\r\n", blacklist_categories=("Cs",)),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "")


@given(size=valid_sizes, copies=st.integers(min_value=1, max_value=100000))
def test_parse_order_valid_properties(size, copies):
    """Valid 'size:copies' string must return uppercase size and integer copies."""
    raw = f"{size}:{copies}"
    parsed_size, parsed_copies = parse_order(raw)

    assert parsed_size == size.strip().upper()
    assert parsed_size == parsed_size.upper()
    assert len(parsed_size) > 0
    assert isinstance(parsed_copies, int) and not isinstance(parsed_copies, bool)
    assert parsed_copies == copies
    assert parsed_copies > 0


@given(size=valid_sizes, copies=st.integers(min_value=-10000, max_value=0))
def test_parse_order_rejects_non_positive_copies(size, copies):
    """Zero or negative copies must raise ValueError."""
    with pytest.raises(ValueError):
        parse_order(f"{size}:{copies}")


@given(
    blank=st.text(alphabet=" \t\r\n", min_size=0, max_size=10),
    copies=st.integers(min_value=1, max_value=1000),
)
def test_parse_order_rejects_empty_size(blank, copies):
    """Empty or whitespace-only print size must raise ValueError."""
    with pytest.raises(ValueError):
        parse_order(f"{blank}:{copies}")


@given(
    size=valid_sizes,
    non_numeric=st.text(alphabet="abcdefghijklmnopqrstuvwxyz!@#$", min_size=1, max_size=10),
)
def test_parse_order_rejects_non_numeric_copies(size, non_numeric):
    """Non-numeric copies must raise ValueError."""
    with pytest.raises(ValueError):
        parse_order(f"{size}:{non_numeric}")


# 2. Properties of file_size_average
@given(sizes=st.lists(st.integers(min_value=0, max_value=10000), min_size=1, max_size=50))
def test_file_size_average_properties(sizes):
    """Integer floor average must match sum(sizes) // len(sizes) and satisfy bounds."""
    raw = ",".join(str(s) for s in sizes)
    avg = file_size_average(raw)

    assert isinstance(avg, int)
    assert avg == sum(sizes) // len(sizes)
    assert min(sizes) <= avg <= max(sizes)

    # Permutation invariance: order of files must not change average
    sorted_raw = ",".join(str(s) for s in sorted(sizes))
    assert file_size_average(sorted_raw) == avg


@given(
    value=st.integers(min_value=0, max_value=5000),
    count=st.integers(min_value=1, max_value=25),
)
def test_file_size_average_constant_values(value, count):
    """A list of identical file sizes must have an average equal to that size."""
    raw = ",".join([str(value)] * count)
    assert file_size_average(raw) == value


@given(whitespace=st.text(alphabet=" \t\r\n", min_size=0, max_size=10))
def test_file_size_average_rejects_empty_input(whitespace):
    """Empty or whitespace-only input must raise ValueError."""
    with pytest.raises(ValueError):
        file_size_average(whitespace)


@given(
    prefix=st.lists(st.integers(min_value=0, max_value=1000), max_size=5),
    negative=st.integers(min_value=-1000, max_value=-1),
    suffix=st.lists(st.integers(min_value=0, max_value=1000), max_size=5),
)
def test_file_size_average_rejects_negative_sizes(prefix, negative, suffix):
    """Negative file sizes must raise ValueError."""
    raw = ",".join(str(x) for x in [*prefix, negative, *suffix])
    with pytest.raises(ValueError):
        file_size_average(raw)


# 3. Properties of payable_amount
@given(
    amount=st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    discount=st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
)
def test_payable_amount_valid_properties(amount, discount):
    """Payable amount must calculate amount * 1.18 - discount clamped to >= 0."""
    raw = f"{amount}|{discount}"
    total = payable_amount(raw)

    expected = round(max(amount * 1.18 - discount, 0.0), 2)
    assert isinstance(total, float)
    assert math.isfinite(total)
    assert total >= 0.0
    assert total == expected


@given(amount=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
def test_payable_amount_zero_discount(amount):
    """Zero discount must yield amount * 1.18 rounded to 2 decimals."""
    raw = f"{amount}|0"
    total = payable_amount(raw)
    assert total == round(amount * 1.18, 2)


@given(
    amount=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    excess=st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
)
def test_payable_amount_excessive_discount_clamps_to_zero(amount, excess):
    """Discount exceeding gross amount + GST must clamp payable amount to 0.0."""
    discount = (amount * 1.18) + excess
    raw = f"{amount}|{discount}"
    assert payable_amount(raw) == 0.0


invalid_float_inputs = st.one_of(
    st.floats(max_value=-0.0001, allow_nan=False, allow_infinity=True),
    st.just(float("nan")),
    st.just(float("inf")),
    st.just(float("-inf")),
)
valid_float_inputs = st.floats(min_value=0.0, max_value=50000.0, allow_nan=False, allow_infinity=False)


@given(
    pair=st.one_of(
        st.tuples(invalid_float_inputs, valid_float_inputs),
        st.tuples(valid_float_inputs, invalid_float_inputs),
        st.tuples(invalid_float_inputs, invalid_float_inputs),
    )
)
def test_payable_amount_rejects_invalid_numbers(pair):
    """Negative, NaN, or infinite numbers must raise ValueError."""
    amount, discount = pair
    with pytest.raises(ValueError):
        payable_amount(f"{amount}|{discount}")
