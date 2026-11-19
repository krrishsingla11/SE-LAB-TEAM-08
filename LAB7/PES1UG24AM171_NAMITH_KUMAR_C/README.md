# Lab 7 – Fuzz Testing

- **Student Name:** Namith Kumar C
- **SRN:** PES1UG24AM171
- **Course:** Software Engineering Lab (UE24CS252AA)
- **Assigned Repository:** `SETAPESU26/L6_L7_46_photo_print_order`
- **Application Scenario:** Photo Print Order (`photo_print_order.py`)

---

## Objective

Apply automated **fuzz testing** and **property-based testing** using Python's **Hypothesis** library and **pytest** to discover input-handling defects, unhandled exceptions, and edge-case crashes in the Photo Print Order application, harden the application with defensive validation, and verify that all functions satisfy their core mathematical and domain invariants across arbitrary, boundary, and malformed inputs.

---

## Files Included

| File / Folder | Description |
|---|---|
| `photo_print_order.py` | Photo Print Order application with robust input validation and bug fixes |
| `test_photo_print_order.py` | Hypothesis fuzz / robustness tests and property-based test suite (15 tests) |
| `requirements.txt` | Python dependencies (`pytest`, `hypothesis`) |
| `README.md` | Lab documentation, defect analysis, test design, and execution instructions |
| `Screenshot/fuzz_testing_result.png` | Terminal execution screenshot showing all 15 tests passing |

---

## Bugs Found by Fuzzing (Original Code)

1. **`parse_order(text)`**:
   - **`NoneType` Crash**: Passing `None` or non-string inputs raised an unhandled `AttributeError: 'NoneType' object has no attribute 'split'`.
   - **Delimiter Unpacking Crashes**: Strings lacking `:` or with multiple `:` caused `ValueError: not enough values to unpack` or `too many values to unpack`.
   - **Empty Size Acceptance**: Empty size inputs (e.g. `":25"`) were accepted and returned empty string `""` without validation.
   - **Negative / Non-Integer Copies**: Non-numeric copy counts raised uncaught `ValueError`, while negative copy counts (`"4x6:-10"`) were accepted despite negative prints being physically invalid.

2. **`file_size_average(sizes_csv)`**:
   - **`NoneType` Crash**: Passing `None` or non-string types raised `AttributeError`.
   - **Empty Input / Zero Division**: Passing empty strings or whitespace caused `ValueError`, or in zero-token cases caused a fatal `ZeroDivisionError: integer division or modulo by zero`.
   - **Malformed Tokens**: Passing non-integer tokens (e.g. `"4,abc,12"`, `"4,,12"`) crashed with `ValueError`.
   - **Negative File Sizes**: Accepted negative file sizes without domain validation.

3. **`payable_amount(text)`**:
   - **`NoneType` Crash**: Passing `None` or non-strings raised `AttributeError`.
   - **Delimiter Format**: Inputs without `|` or with extra `|` raised unpacking `ValueError`.
   - **Non-Finite Floats**: Passing `NaN`, `Infinity`, or non-numeric tokens caused unhandled `ValueError` or produced nonsensical `NaN` calculations.
   - **Negative Financial Values**: Accepted negative amounts or discounts without validation.

---

## Functions Covered and Expected Behavior

1. **`parse_order(text)`**
   - Accepts a string in `size:copies` format (e.g., `"4x6:25"`).
   - Validates that `text` is a string, splits on `:` with exactly two components, trims whitespace, verifies size is non-empty, and verifies copies is a strictly positive integer (`copies > 0`).
   - Returns `(size.upper(), copies)` as a `(str, int)` tuple.
   - Raises `TypeError` for non-string inputs and `ValueError` for malformed delimiters, empty size, or non-positive/non-integer copies.

2. **`file_size_average(sizes_csv)`**
   - Accepts a comma-separated string of file sizes in MB (e.g., `"4,8,12"`).
   - Validates that `sizes_csv` is a string, verifies it is non-empty, parses all tokens as non-negative integers (`>= 0`), and computes the integer floor average (`sum(values) // len(values)`).
   - Raises `TypeError` for non-string inputs and `ValueError` for empty/whitespace input, consecutive/trailing commas, non-integer tokens, or negative sizes.

3. **`payable_amount(text)`**
   - Accepts a string in `amount|discount` format (e.g., `"450|50"`).
   - Validates that `text` is a string, splits on `|` into exactly two components, parses finite non-negative numbers (`>= 0`), applies 18% GST (`amount * 1.18 - discount`), clamps the payable amount to non-negative (`>= 0.0`), and rounds to 2 decimal places.
   - Raises `TypeError` for non-string inputs and `ValueError` for malformed delimiters, non-numeric values, `NaN`, `Infinity`, or negative values.

---

## Fuzz Testing and Property-Based Testing

The test suite in `test_photo_print_order.py` contains **15 Hypothesis tests** structured into two main sections:

### A. Fuzz / Robustness Tests (No Unexpected Crashes)
1. `test_parse_order_no_crash`: Tests arbitrary Unicode strings, `None`, integers, floats, booleans, and malformed strings. Must either return a valid `(str, int)` tuple with positive copies or raise handled exceptions (`ValueError`, `TypeError`).
2. `test_file_size_average_no_crash`: Tests arbitrary strings, `None`, mixed types, and random CSV strings. Must either return a non-negative integer or raise `ValueError`/`TypeError`—never crashing with `ZeroDivisionError`.
3. `test_payable_amount_no_crash`: Tests arbitrary strings, `None`, mixed types, and random pipe-separated floats (including `NaN` and `Inf`). Must either return a finite float `>= 0.0` or raise `ValueError`/`TypeError`.

### B. Property-Based Tests
- **`parse_order` Properties:**
  4. `test_parse_order_valid_properties`: Round-trip verification that valid generated size and positive integer copies return normalized uppercase size and exact integer copies.
  5. `test_parse_order_rejects_non_positive_copies`: Rejects zero and negative copies with `ValueError`.
  6. `test_parse_order_rejects_empty_size`: Rejects blank or whitespace-only sizes with `ValueError`.
  7. `test_parse_order_rejects_non_numeric_copies`: Rejects non-numeric copy tokens with `ValueError`.
- **`file_size_average` Properties:**
  8. `test_file_size_average_properties`: Verifies integer floor average formula, mathematical boundedness (`min <= avg <= max`), and permutation invariance (`avg(shuffled) == avg(original)`).
  9. `test_file_size_average_constant_values`: Verifies that a list of identical values produces that exact value.
  10. `test_file_size_average_rejects_empty_input`: Rejects empty strings and whitespace with `ValueError`.
  11. `test_file_size_average_rejects_negative_sizes`: Rejects negative integers with `ValueError`.
- **`payable_amount` Properties:**
  12. `test_payable_amount_valid_properties`: Verifies calculation formula `round(max(amount * 1.18 - discount, 0.0), 2)` across arbitrary valid ranges.
  13. `test_payable_amount_zero_discount`: Verifies exact GST computation when discount is 0.
  14. `test_payable_amount_excessive_discount_clamps_to_zero`: Verifies that discounts exceeding gross total clamp the payable amount strictly to `0.0`.
  15. `test_payable_amount_rejects_invalid_numbers`: Rejects negative numbers, `NaN`, and `Infinity` with `ValueError`.

---

## Dependencies

Listed in `requirements.txt`:
```
pytest
hypothesis
```

---

## Installation and Execution (Windows PowerShell)

Run these commands from this directory:

1. Install dependencies:
```powershell
py -m pip install -r requirements.txt
```

2. Run the fuzz and property-based test suite:
```powershell
py -m pytest -v
```

---

## Evidence

The test suite executed successfully with all 15 tests passing:
- Screenshot saved at: `Screenshot/fuzz_testing_result.png`
