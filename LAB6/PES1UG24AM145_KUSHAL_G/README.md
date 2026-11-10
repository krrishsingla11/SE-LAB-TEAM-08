# Lab 6: Code and Branch Coverage Analysis

## Student Details
- **Student Name**: Kushal G
- **SRN**: PES1UG24AM145
- **Assigned Scenario**: Gym Membership
- **Application Module**: `gym_membership.py`
- **Starter Test File**: `test_gym_membership.py`

---

## Deliverable Test Suites

1. **Code Coverage Test Suite**:
   - **File**: `CodeCoverageTest_PES1UG24AM145_application.py`
   - **Description**: Independent pytest suite testing all statements, boundaries, valid alternatives, exceptions, and realistic execution paths of `gym_membership.py`.

2. **Branch Coverage Test Suite**:
   - **File**: `BranchCoverageTest_PES1UG24AM145_application.py`
   - **Description**: Comprehensive decision-focused pytest suite specifically testing every True and False conditional evaluation branch.

---

## Commands to Run Tests and Coverage Reports

### 1. Code Coverage (Line Coverage)
Run pytest with line coverage tracking:
```bash
coverage run --source=gym_membership -m pytest CodeCoverageTest_PES1UG24AM145_application.py
```

Display line coverage report with missing line analysis:
```bash
coverage report -m
```

### 2. Branch Coverage
Run pytest with branch coverage tracking:
```bash
coverage run --branch --source=gym_membership -m pytest BranchCoverageTest_PES1UG24AM145_application.py
```

Display branch coverage report with partial branch analysis:
```bash
coverage report -m
```

---

## Coverage Analysis & Results

| Analysis Type | Target | Achieved Percentage | Total Statements / Branches | Missed / Partial | Status |
|---------------|--------|---------------------|-----------------------------|------------------|--------|
| **Line Coverage** | $\ge 90\%$ | **100%** | 35 statements | 0 missed | Passed |
| **Branch Coverage** | $\ge 90\%$ | **100%** | 26 branches | 0 partial | Passed |

### Key Observations:
- **Baseline Starter Tests**: Achieved only 43% line coverage (missed 20 statements) and 38% branch coverage.
- **Code Coverage Suite**: 84 test cases executed, systematically covering all input conditions, boundary values, and exceptions. Achieved **100% line coverage** on `gym_membership.py`.
- **Branch Coverage Suite**: 33 targeted test cases executed, evaluating every `if`/`elif`/`else` condition to both boolean states. Achieved **100% branch coverage** on `gym_membership.py`.

---

## Detailed Branch Coverage Analysis

All 13 decision points (26 branch outcomes) in `gym_membership.py` are fully evaluated:

| # | Function | Decision / Predicate | True Branch | False Branch |
|---|----------|----------------------|-------------|--------------|
| 1 | `membership_cost` | `if plan not in PLAN_PRICE:` | Unknown plan raises `ValueError("unknown plan")` | Known plan proceeds |
| 2 | `membership_cost` | `if age < 14:` | Age < 14 raises `ValueError("too young")` | Age $\ge 14$ proceeds |
| 3 | `membership_cost` | `if age >= 60:` | Senior 25% discount applied | Age < 60 evaluates student check |
| 4 | `membership_cost` | `elif is_student:` | Student 10% discount applied | Non-student: full base price |
| 5 | `membership_cost` | `if with_trainer:` | Adds 2000 trainer fee | Trainer fee bypassed |
| 6 | `membership_cost` | `if plan == "yearly":` (nested) | Yearly plan receives 500 trainer rebate | Non-yearly plan keeps full 2000 fee |
| 7 | `can_enter` | `if not plan_active:` | Returns `False` | Proceeds to hour checks |
| 8a | `can_enter` | `hour < 5` (in compound OR) | Short-circuits to return `False` | Evaluates second operand |
| 8b | `can_enter` | `hour > 22` (in compound OR) | Returns `False` | Valid hour range [5, 22] proceeds |
| 9 | `can_enter` | `if is_women_only_slot:` | Evaluates `gender == "F"` (`True` for F, `False` otherwise) | Bypassed, falls through to `return True` |
| 10 | `bmi_category` | `if height_m <= 0:` | Height $\le 0$ raises `ValueError("invalid height")` | Height > 0 calculates BMI |
| 11 | `bmi_category` | `if bmi < 18.5:` | Returns `"underweight"` | Proceeds to next check |
| 12 | `bmi_category` | `elif bmi < 25:` | Returns `"normal"` | Proceeds to next check |
| 13 | `bmi_category` | `elif bmi < 30:` | Returns `"overweight"` | Falls through to return `"obese"` |

---

## Terminal Screenshots
- Code Coverage Terminal Result: `code_coverage_terminal.png`
- Branch Coverage Terminal Result: `branch_coverage_terminal.png`
