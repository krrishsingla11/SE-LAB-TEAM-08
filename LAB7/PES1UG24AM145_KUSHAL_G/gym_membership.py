import math


def parse_plan(code):
    """Parse a 'PLAN-MONTHS' string into (UPPERCASE_PLAN, positive_months)."""
    if not isinstance(code, str):
        raise TypeError("Plan code must be a string.")

    parts = code.split("-")
    if len(parts) != 2:
        raise ValueError("Plan code must be in 'PLAN-MONTHS' format.")

    plan = parts[0].strip()
    months_str = parts[1].strip()
    if not plan:
        raise ValueError("Plan name must not be empty.")
    if not (months_str.isascii() and months_str.isdigit()):
        raise ValueError("Months must be a positive integer.")

    months = int(months_str)
    if months <= 0:
        raise ValueError("Months must be a positive integer.")

    return plan.upper(), months


def calculate_bmi(data):
    """Parse 'weight,height' and return BMI rounded to one decimal place."""
    if not isinstance(data, str):
        raise TypeError("Input data must be a string.")

    parts = data.split(",")
    if len(parts) != 2:
        raise ValueError("Input must be in 'weight,height' format.")

    weight = float(parts[0].strip())
    height = float(parts[1].strip())
    if not (math.isfinite(weight) and math.isfinite(height)):
        raise ValueError("Weight and height must be finite numbers.")
    if weight <= 0 or height <= 0:
        raise ValueError("Weight and height must be positive numbers.")

    try:
        denominator = height ** 2
    except OverflowError as exc:
        raise ValueError("Height is out of supported range.") from exc

    if denominator == 0 or not math.isfinite(denominator):
        raise ValueError("Height is out of supported range.")

    bmi = weight / denominator
    if not math.isfinite(bmi):
        raise ValueError("Calculated BMI is out of supported range.")

    return round(bmi, 1)


def average_workout(minutes):
    """Parse space-separated non-negative integers and return floor average."""
    if not isinstance(minutes, str):
        raise TypeError("Workout minutes must be a string.")

    tokens = minutes.split()
    if not tokens:
        raise ValueError("At least one workout duration is required.")

    values = [int(m) for m in tokens]
    if any(v < 0 for v in values):
        raise ValueError("Workout minutes must be non-negative.")

    return sum(values) // len(values)


def main():
    print("==== Running parse_plan ====")
    user_input = input("Enter a plan code (e.g. GOLD-12): ")
    result = parse_plan(user_input)
    print("Plan and Months:", result)

    print("\n==== Running calculate_bmi ====")
    user_input = input("Enter weight and height (e.g. 70,1.75): ")
    result = calculate_bmi(user_input)
    print("BMI:", result)

    print("\n==== Running average_workout ====")
    user_input = input("Enter workout minutes separated by spaces (e.g. 45 60 30): ")
    result = average_workout(user_input)
    print("Average Minutes:", result)


if __name__ == "__main__":
    main()
