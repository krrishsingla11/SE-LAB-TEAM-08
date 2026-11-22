# Lab 6: Code and Branch Coverage Analysis

## Student Details
- **Student Name**: Kishan K Shenoy
- **SRN**: PES1UG24AM138
- **Course**: Software Engineering Lab (UE24CS252AA)
- **Assigned Repository**: `SETAPESU26/L6_L7_14_library_fines`
- **Application Scenario**: Scenario 14 — Library Fines
- **Application Module**: `library_fines.py`
- **Starter Test File**: `test_library_fines.py`

---

## Deliverable Test Suites

1. **Code Coverage Test Suite**:
   - **File**: `CodeCoverageTest_PES1UG24AM138_application.py`
   - **Description**: Comprehensive pytest suite systematically exercising every executable statement, dictionary constant, boundary condition, and exception branch in `library_fines.py`.
   - **Total Tests**: 24 test cases.
   - **Line Coverage Achieved**: **100%** (32 / 32 statements covered).

2. **Branch Coverage Test Suite**:
   - **File**: `BranchCoverageTest_PES1UG24AM138_application.py`
   - **Description**: Decision-focused pytest suite specifically testing every True and False conditional branch across member validation, day limits, overdue calculations, fine capping, damage fees, borrowing rules, and renewal criteria.
   - **Total Tests**: 10 comprehensive test functions.
   - **Branch Coverage Achieved**: **100%** (22 / 22 decision branches evaluated).

---

## Commands to Run Tests and Generate Coverage Reports

### 1. Code Coverage (Line Coverage)
Run pytest with code coverage tracking:
```bash
coverage run --source=library_fines -m pytest CodeCoverageTest_PES1UG24AM138_application.py
```

Display line coverage report with missing line breakdown:
```bash
coverage report -m
```

### 2. Branch Coverage
Run pytest with branch coverage tracking:
```bash
coverage run --branch --source=library_fines -m pytest BranchCoverageTest_PES1UG24AM138_application.py
```

Display branch coverage report with partial branch breakdown:
```bash
coverage report -m
```

---

## Coverage Analysis & Results Summary

| Metric | Target | Achieved Result | Evaluation |
| :--- | :--- | :--- | :--- |
| **Statement / Line Coverage** | $\ge 90\%$ | **100%** (32 / 32 Statements) | Full Coverage |
| **Branch / Decision Coverage** | $\ge 90\%$ | **100%** (22 / 22 Branches) | Full Coverage |
| **Missing Statements / Branches** | 0 | **0** | Complete Test Suite |

---

## Deliverables in this Directory

- `library_fines.py`: Target application module.
- `test_library_fines.py`: Baseline starter test file.
- `CodeCoverageTest_PES1UG24AM138_application.py`: Line coverage test suite (100%).
- `BranchCoverageTest_PES1UG24AM138_application.py`: Branch coverage test suite (100%).
- `code_coverage_terminal.png`: Terminal screenshot of code coverage run and report.
- `branch_coverage_terminal.png`: Terminal screenshot of branch coverage run and report.
- `LAB6_PES1UG24AM138_Kishan_K_Shenoy.pdf`: Formal Lab 6 report document.
- `README.md`: This documentation file.
