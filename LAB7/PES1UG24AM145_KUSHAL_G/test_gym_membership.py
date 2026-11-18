import math
import pytest
from hypothesis import given, strategies as st

from gym_membership import parse_plan, calculate_bmi, average_workout

ALLOWED_EXCEPTIONS = (ValueError, TypeError)

UNEXPECTED_INPUTS = st.one_of(
    st.text(),
    st.none(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.booleans(),
    st.lists(st.text(), max_size=3),
)


# ---------------------------------------------------------------------------
# A. Fuzz / Robustness Tests (No Unexpected Crashes)
# ---------------------------------------------------------------------------

@given(UNEXPECTED_INPUTS)
def test_parse_plan_no_crash(s):
    try:
        result = parse_plan(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(result, tuple)
    assert len(result) == 2
    plan, months = result
    assert isinstance(plan, str)
    assert len(plan) > 0
    assert plan == plan.upper()
    assert isinstance(months, int) and not isinstance(months, bool)
    assert months > 0


@given(
    st.one_of(
        UNEXPECTED_INPUTS,
        st.builds(
            lambda w, h: f"{w},{h}",
            st.floats(allow_nan=True, allow_infinity=True),
            st.floats(allow_nan=True, allow_infinity=True),
        ),
    )
)
def test_calculate_bmi_no_crash(s):
    try:
        bmi = calculate_bmi(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(bmi, float)
    assert math.isfinite(bmi)
    assert bmi >= 0.0
    assert bmi == round(bmi, 1)


@given(
    st.one_of(
        UNEXPECTED_INPUTS,
        st.builds(
            lambda nums: " ".join(str(n) for n in nums),
            st.lists(st.integers(min_value=-1000, max_value=10000), max_size=10),
        ),
    )
)
def test_average_workout_no_crash(s):
    try:
        avg = average_workout(s)
    except ALLOWED_EXCEPTIONS:
        return

    assert isinstance(avg, int) and not isinstance(avg, bool)
    assert avg >= 0


# ---------------------------------------------------------------------------
# B. Property-Based Tests
# ---------------------------------------------------------------------------

valid_plan_names = st.text(
    alphabet=st.characters(blacklist_characters="-", blacklist_categories=("Cs",)),
    min_size=1,
    max_size=25,
).filter(lambda name: name.strip() != "")


@given(plan_name=valid_plan_names, months=st.integers(min_value=1, max_value=1200))
def test_parse_plan_valid_properties(plan_name, months):
    code = f"{plan_name}-{months}"
    plan, parsed_months = parse_plan(code)

    assert plan == plan_name.strip().upper()
    assert plan == plan.upper()
    assert len(plan) > 0
    assert isinstance(parsed_months, int) and not isinstance(parsed_months, bool)
    assert parsed_months == months
    assert parsed_months > 0


@given(plan_name=valid_plan_names, months=st.integers(min_value=-1000, max_value=0))
def test_parse_plan_rejects_non_positive_months(plan_name, months):
    with pytest.raises(ValueError):
        parse_plan(f"{plan_name}-{months}")


@given(
    blank=st.text(alphabet=" \t\r\n", min_size=0, max_size=10),
    months=st.integers(min_value=1, max_value=1200),
)
def test_parse_plan_rejects_empty_plan_name(blank, months):
    with pytest.raises(ValueError):
        parse_plan(f"{blank}-{months}")


@given(
    weight=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    height=st.floats(min_value=0.3, max_value=3.0, allow_nan=False, allow_infinity=False),
)
def test_calculate_bmi_valid_properties(weight, height):
    data = f"{weight},{height}"
    bmi = calculate_bmi(data)

    expected = round(weight / (height ** 2), 1)
    assert isinstance(bmi, float)
    assert math.isfinite(bmi)
    assert bmi > 0.0
    assert bmi == expected


@given(
    w1=st.floats(min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    w_delta=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    h1=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
    h_delta=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_calculate_bmi_monotonicity(w1, w_delta, h1, h_delta):
    w2 = w1 + w_delta
    h2 = h1 + h_delta

    assert calculate_bmi(f"{w1},{h1}") <= calculate_bmi(f"{w2},{h1}")
    assert calculate_bmi(f"{w1},{h2}") <= calculate_bmi(f"{w1},{h1}")


invalid_float = st.one_of(
    st.floats(max_value=0.0, allow_nan=False, allow_infinity=True),
    st.just(float("nan")),
    st.just(float("inf")),
)
positive_float = st.floats(min_value=0.1, max_value=500.0, allow_nan=False, allow_infinity=False)


@given(
    pair=st.one_of(
        st.tuples(invalid_float, positive_float),
        st.tuples(positive_float, invalid_float),
        st.tuples(invalid_float, invalid_float),
    )
)
def test_calculate_bmi_rejects_invalid_numbers(pair):
    weight, height = pair
    with pytest.raises(ValueError):
        calculate_bmi(f"{weight},{height}")


@given(durations=st.lists(st.integers(min_value=0, max_value=1440), min_size=1, max_size=50))
def test_average_workout_properties(durations):
    raw = " ".join(str(d) for d in durations)
    avg = average_workout(raw)

    assert isinstance(avg, int)
    assert avg == sum(durations) // len(durations)
    assert min(durations) <= avg <= max(durations)

    sorted_raw = " ".join(str(d) for d in sorted(durations))
    assert average_workout(sorted_raw) == avg


@given(
    value=st.integers(min_value=0, max_value=1440),
    count=st.integers(min_value=1, max_value=30),
)
def test_average_workout_constant_input(value, count):
    raw = " ".join([str(value)] * count)
    assert average_workout(raw) == value


@given(
    whitespace=st.text(alphabet=" \t\r\n", min_size=0, max_size=10),
)
def test_average_workout_rejects_empty_input(whitespace):
    with pytest.raises(ValueError):
        average_workout(whitespace)


@given(
    prefix=st.lists(st.integers(min_value=0, max_value=1440), max_size=10),
    negative=st.integers(min_value=-1000, max_value=-1),
    suffix=st.lists(st.integers(min_value=0, max_value=1440), max_size=10),
)
def test_average_workout_rejects_negative_minutes(prefix, negative, suffix):
    raw = " ".join(str(x) for x in [*prefix, negative, *suffix])
    with pytest.raises(ValueError):
        average_workout(raw)
