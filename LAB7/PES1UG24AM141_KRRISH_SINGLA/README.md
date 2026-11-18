# Lab 7 – Fuzz Testing

**Student:** Krrish Singla  
**SRN:** PES1UG24AM141  
**Problem:** Electricity Bill

## Objective
Use Hypothesis-based fuzz testing to check that the Electricity Bill functions handle a wide range of inputs safely and satisfy their expected properties.

## Files
- `electricity_bill.py` – defensive implementations of the three functions under test.
- `test_electricity_bill.py` – Hypothesis fuzz tests and property-based tests.
- `requirements.txt` – Python test dependencies.
- `Screenshot/fuzz_testing_result.png` – terminal screenshot of the passing test run.

## Bugs found by fuzzing (original code)
1. `units_consumed` – crashed on `None`, on strings without exactly one `:`, and on non-numeric readings (`AttributeError` / `ValueError`).
2. `daily_average` – crashed on `None`, on non-numeric entries, and on empty input (`ValueError` / `ZeroDivisionError`).
3. `tariff_rate` – crashed on `None`, on codes without exactly one `-`, and on unknown categories or slabs (`AttributeError` / `ValueError` / `KeyError`).

## Functions covered
1. `units_consumed(reading)` – parses `previous:current` and returns the difference; malformed input or a current reading lower than the previous one returns `None`.
2. `daily_average(units_csv)` – averages the valid non-negative entries, rounded to 2 decimals; invalid entries are ignored and empty/invalid input returns `0.0`.
3. `tariff_rate(code)` – returns `RATE × SLAB` for codes like `DOM-A` (case-insensitive); invalid or unknown codes return `0`.

## Run tests (Windows PowerShell / VS Code terminal)
Run these commands from this directory:

```powershell
py -m pip install -r requirements.txt
py -m pytest -v
```

Hypothesis generates many test inputs automatically for each fuzz test. The suite has three no-crash fuzz tests and three property tests.
