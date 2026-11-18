# Lab 7 – Fuzz Testing

- **Student Name:** Kushal G
- **SRN:** PES1UG24AM145
- **Problem:** Gym Membership (`L6_L7_21_gym_membership`)

---

## Objective

Apply automated **fuzz testing** and **property-based testing** using Python's **Hypothesis** library and **pytest** to uncover input-handling defects, edge-case crashes, and validation gaps in the Gym Membership application, fix the discovered bugs, and verify that all functions behave reliably across valid, boundary, and malformed inputs.

---

## Files Included

| File / Folder | Description |
|---|---|
| `gym_membership.py` | Gym Membership application with input validation and bug fixes |
| `test_gym_membership.py` | Hypothesis fuzz/robustness tests and property-based tests |
| `requirements.txt` | Python dependencies (`pytest`, `hypothesis`) |
| `README.md` | Lab documentation, test coverage, and execution instructions |
| `Screenshot/fuzz_testing_result.png` | Screenshot of successful `pytest` execution in PowerShell |

---

## Functions Covered and Expected Behaviour

1. **`parse_plan(code)`**
   - Accepts a string in `PLAN-MONTHS` format (e.g., `"GOLD-12"`).
   - Trims surrounding whitespace, requires a non-empty plan name and a positive ASCII integer for months (`> 0`).
   - Returns `(PLAN_UPPERCASE, months)` as a `(str, int)` tuple.
   - Raises `TypeError` for non-string inputs and `ValueError` for malformed formats, empty plan names, or non-positive/non-integer months.

2. **`calculate_bmi(data)`**
   - Accepts a comma-separated `"weight,height"` string (e.g., `"70,1.75"`).
   - Parses `weight` and `height` as finite positive floats (`> 0`, rejecting `0`, negatives, `NaN`, `Inf`, and overflow/underflow edge cases).
   - Computes `weight / (height ** 2)` and returns the BMI rounded to 1 decimal place (`float`).
   - Raises `TypeError` for non-string inputs and `ValueError` for malformed strings or invalid/out-of-range numeric values.

3. **`average_workout(minutes)`**
   - Accepts a string containing one or more space-separated non-negative integers (e.g., `"45 60 30"`).
   - Computes and returns the integer floor average (`sum(values) // len(values)`).
   - Raises `TypeError` for non-string inputs and `ValueError` for empty/whitespace-only inputs, non-integer tokens, or negative durations.

---

## Fuzz Testing and Property-Based Testing

The test suite in `test_gym_membership.py` contains **13 Hypothesis tests** split into two categories:

### A. Fuzz / Robustness Tests (No Unexpected Crashes)
- `test_parse_plan_no_crash`
- `test_calculate_bmi_no_crash`
- `test_average_workout_no_crash`

These tests feed arbitrary Unicode strings, `None`, integers, floats (including `NaN` and `Inf`), booleans, lists, and malformed delimited strings to each function. Each function must either return a valid output satisfying basic invariants or raise only explicit validation exceptions (`ValueError` or `TypeError`)—never `AttributeError`, `ZeroDivisionError`, or `OverflowError`.

### B. Property-Based Tests
- **`parse_plan`:**
  - `test_parse_plan_valid_properties`: Verifies uppercase plan normalization, positive `int` month parsing, and exact round-trip matching for generated valid inputs.
  - `test_parse_plan_rejects_non_positive_months`: Verifies `ValueError` when months `<= 0`.
  - `test_parse_plan_rejects_empty_plan_name`: Verifies `ValueError` when the plan name is empty or whitespace-only.
- **`calculate_bmi`:**
  - `test_calculate_bmi_valid_properties`: Verifies finite positive float output matching `round(weight / (height ** 2), 1)`.
  - `test_calculate_bmi_monotonicity`: Verifies BMI is non-decreasing with weight and non-increasing with height.
  - `test_calculate_bmi_rejects_invalid_numbers`: Verifies `ValueError` for zero, negative, `NaN`, and `Inf` inputs.
- **`average_workout`:**
  - `test_average_workout_properties`: Verifies integer floor average, boundedness (`min <= avg <= max`), and permutation invariance.
  - `test_average_workout_constant_input`: Verifies constant-list average equals the repeated value.
  - `test_average_workout_rejects_empty_input`: Verifies `ValueError` on empty or whitespace-only input.
  - `test_average_workout_rejects_negative_minutes`: Verifies `ValueError` when any duration is negative.

---

## Dependencies

Listed in `requirements.txt`:
- `pytest`
- `hypothesis`

---

## Installation and Execution (Windows PowerShell)

Open PowerShell inside the `Lab 7` directory (`L6_L7_21_gym_membership-main\Lab 7`) and run the following commands separately:

1. Install dependencies:
```powershell
py -m pip install -r requirements.txt
```

2. Run the fuzz and property-based tests:
```powershell
py -m pytest -v
```

---

## Evidence

Save a screenshot of the successful terminal test run (`py -m pytest -v` showing all 13 tests passing) at:

`Screenshot/fuzz_testing_result.png`
