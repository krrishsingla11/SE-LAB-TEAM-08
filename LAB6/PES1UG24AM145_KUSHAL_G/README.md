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

## Terminal Screenshots
- Code Coverage Terminal Result: `code_coverage_terminal.png`
- Branch Coverage Terminal Result: `branch_coverage_terminal.png`
