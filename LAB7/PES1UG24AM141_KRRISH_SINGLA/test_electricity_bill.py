from hypothesis import given, strategies as st

from electricity_bill import units_consumed, daily_average, tariff_rate, RATES, SLAB


# Fuzz tests: arbitrary strings (and None) must never crash the functions.
ANY_INPUT = st.one_of(st.text(), st.none())


@given(ANY_INPUT)
def test_units_consumed_no_crash(s):
    result = units_consumed(s)
    assert result is None or (isinstance(result, int) and result >= 0)


@given(ANY_INPUT)
def test_daily_average_no_crash(s):
    result = daily_average(s)
    assert isinstance(result, float)
    assert result >= 0


@given(ANY_INPUT)
def test_tariff_rate_no_crash(s):
    result = tariff_rate(s)
    assert isinstance(result, int)
    assert result >= 0


# Property tests: valid inputs must preserve the expected behaviour.
@given(st.integers(min_value=0, max_value=10**9),
       st.integers(min_value=0, max_value=10**9))
def test_units_consumed_valid_readings(previous, extra):
    current = previous + extra
    assert units_consumed(f"{previous}:{current}") == extra


@given(st.lists(st.integers(min_value=0, max_value=10**6), min_size=1, max_size=30))
def test_daily_average_matches_rule(units):
    csv_value = ','.join(str(u) for u in units)
    assert daily_average(csv_value) == round(sum(units) / len(units), 2)


@given(st.sampled_from(sorted(RATES)), st.sampled_from(sorted(SLAB)), st.booleans())
def test_tariff_rate_valid_codes(category, slab, lowercase):
    code = f"{category}-{slab}"
    if lowercase:
        code = code.lower()
    assert tariff_rate(code) == RATES[category] * SLAB[slab]
