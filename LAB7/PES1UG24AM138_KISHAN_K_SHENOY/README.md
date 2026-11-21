# Lab 7 – Fuzz Testing

- **Student Name:** Kishan K Shenoy
- **SRN:** PES1UG24AM138
- **Course:** Software Engineering Lab (UE24CS252AA)
- **Assigned Repository:** `SETAPESU26/L6_L7_14_library_fines`
- **Application Scenario:** Scenario 14 — Library Fines (`library_fines.py`)

---

## Objective

Apply automated **fuzz testing** and **property-based testing** using Python's **Hypothesis** library and **pytest** to discover input-handling defects, unhandled exceptions, and boundary crashes in the Library Fines application, harden the functions defensively against malformed data, and verify that all core mathematical and domain invariants hold across arbitrary inputs.

---

## Files Included

| File / Folder | Description |
|---|---|
| `library_fines.py` | Library fines application with defensive validation and bug fixes |
| `test_library_fines.py` | Hypothesis fuzz / robustness tests and property-based test suite (15 tests) |
| `requirements.txt` | Python dependencies (`pytest`, `hypothesis`) |
| `README.md` | Lab documentation, defect analysis, test design, and execution instructions |
| `Screenshot/fuzz_testing_result.png` | Terminal execution screenshot showing all 15 tests passing |
| `LAB7_PES1UG24AM138_Kishan_K_Shenoy.pdf` | Formal Lab 7 PDF report document |

---

## Bugs Found by Fuzzing (Original Code)

1. **`parse_member_id(member_id)`**:
   - **`NoneType` Crash**: Passing `None` or non-string inputs raised an unhandled `AttributeError: 'NoneType' object has no attribute 'split'`.
   - **Delimiter Unpacking Crashes**: Strings lacking `-` or with multiple `-` caused `ValueError: not enough values to unpack` or `too many values to unpack`.
   - **Empty Type Acceptance**: Empty type inputs (e.g. `"-1023"`) were accepted without checking for non-empty identifier.
   - **Non-Numeric / Negative ID**: Non-numeric member numbers caused unhandled `ValueError`, while negative numbers were accepted without domain validation.

2. **`total_fine(days_csv)`**:
   - **`NoneType` Crash**: Passing `None` or non-string types raised `AttributeError`.
   - **Empty Input / Zero Tokens**: Passing empty strings or whitespace caused `ValueError` when splitting on comma.
   - **Malformed Tokens**: Passing non-integer tokens (e.g. `"10,abc,20"`, `"10,,20"`) crashed with unhandled `ValueError`.
   - **Negative Days**: Accepted negative day entries without domain validation.

3. **`shelf_code(title)`**:
   - **`NoneType` Crash**: Passing `None` or non-strings raised `AttributeError`.
   - **Index Out of Range**: Passing empty strings, whitespace, or single-word titles crashed fatally with `IndexError: list index out of range`.

---

## Functions Covered and Expected Behavior

1. **`parse_member_id(member_id)`**
   - Accepts a string in `type-number` format (e.g., `"STU-1023"`).
   - Validates that `member_id` is a string, splits on `-` with exactly two components, trims whitespace, verifies type is non-empty, and verifies number is a non-negative integer.
   - Returns `(member_type.upper(), number)` as a `(str, int)` tuple.
   - Raises `TypeError` for non-string inputs and `ValueError` for malformed delimiters, empty type, or negative/non-integer numbers.

2. **`total_fine(days_csv)`**
   - Accepts a comma-separated string of days kept for each book (e.g., `"10,20,30"`).
   - Validates input, parses each day, verifies non-negative integers, and computes 2 units per day for any day > 14.
   - Returns total fine as non-negative `int`.
   - Raises `TypeError` for non-string inputs and `ValueError` for empty inputs or negative numbers.

3. **`shelf_code(title)`**
   - Accepts a book title string with at least two words.
   - Trims whitespace, verifies at least two words, and extracts the first character of each word.
   - Returns two-character uppercase string `(words[0][0] + words[1][0]).upper()`.
   - Raises `TypeError` for non-string inputs and `ValueError` for fewer than two words.

---

## Test Design & Verification

The test suite in `test_library_fines.py` comprises 15 automated test cases:
- **Fuzz / Robustness Tests**: Exercises all three functions with arbitrary inputs (`st.text()`, `st.none()`, `st.integers()`, `st.floats()`, `st.booleans()`, `st.lists()`). Ensures functions only raise allowable domain exceptions (`(ValueError, TypeError)`) and never unhandled fatal crashes.
- **Property-Based Invariants**:
  - `parse_member_id`: Invariance of uppercase conversion, numeric round-trip, rejection of negative numbers and empty types.
  - `total_fine`: Zero fine for on-time books ($\le 14$ days), exact formula matching, additivity property ($fine(A + B) == fine(A) + fine(B)$), rejection of empty and negative inputs.
  - `shelf_code`: Two-word initial extraction, prefix invariance for titles $> 2$ words, rejection of single-word and empty titles.

---

## How to Run Tests

Run the full Hypothesis test suite:
```powershell
py -m pytest -v
```
