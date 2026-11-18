RATES = {"DOM": 3, "COM": 6}
SLAB = {"A": 1, "B": 2}


def units_consumed(reading):
    """Parse 'previous:current' meter readings and return units consumed.

    Returns None if the input is malformed or the current reading is lower
    than the previous one.
    """
    if not isinstance(reading, str):
        return None

    parts = reading.split(':')
    if len(parts) != 2:
        return None

    try:
        previous, current = (int(part.strip()) for part in parts)
    except ValueError:
        return None

    if previous < 0 or current < previous:
        return None
    return current - previous


def daily_average(units_csv):
    """Return the average of the valid non-negative integers in a CSV string.

    Invalid entries are ignored. Returns 0.0 if there is nothing to average.
    """
    if not isinstance(units_csv, str):
        return 0.0

    units = []
    for item in units_csv.split(','):
        try:
            value = int(item.strip())
        except ValueError:
            continue
        if value >= 0:
            units.append(value)

    if not units:
        return 0.0
    return round(sum(units) / len(units), 2)


def tariff_rate(code):
    """Return the per-unit rate for a code such as 'DOM-A'.

    Returns 0 if the code is malformed or the category/slab is unknown.
    """
    if not isinstance(code, str):
        return 0

    parts = code.split('-')
    if len(parts) != 2:
        return 0

    category, slab = (part.strip().upper() for part in parts)
    if category not in RATES or slab not in SLAB:
        return 0
    return RATES[category] * SLAB[slab]


def main():
    print("==== Running units_consumed ====")
    user_input = input("Enter meter readings as previous:current (e.g. 1200:1350): ")
    result = units_consumed(user_input)
    print("Units Consumed:", result)

    print("\n==== Running daily_average ====")
    user_input = input("Enter daily units as CSV (e.g. 5,7,6): ")
    result = daily_average(user_input)
    print("Daily Average:", result)

    print("\n==== Running tariff_rate ====")
    user_input = input("Enter a tariff code (e.g. DOM-A): ")
    result = tariff_rate(user_input)
    print("Rate per Unit:", result)


if __name__ == "__main__":
    main()
