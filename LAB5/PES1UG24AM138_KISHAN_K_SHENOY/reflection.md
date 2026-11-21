# Lab 5: Static Code Analysis — Personal Reflection

- **Student:** Kishan K Shenoy
- **SRN:** PES1UG24AM138
- **Scenario:** 14 — Applicant Tracking System
- **Program File:** `recruitment_tracker.py`

---

## 1. Context and Approach

The official Lab 5 handout references *"Answers to reflection questions provided in the lab"* under deliverables. This document presents a comprehensive, structured personal reflection grounded directly in the official **Lab 5 Learning Outcomes**:
1. Understanding the purpose and scope of static code analysis.
2. Identifying and resolving common Python programming issues.
3. Effectively using Pylint, Bandit, and Flake8 on an assigned codebase.
4. Interpreting static analysis reports and applying fixes based on issue severity.
5. Evaluating the contribution of static analysis to overall code quality, security, and maintainability.

---

## 2. Purpose and Scope of Static Code Analysis

Static analysis involves evaluating source code without executing it, enabling early detection of defects, security vulnerabilities, and stylistic inconsistencies before code reaches runtime or production.

In this lab, applying static analysis to `recruitment_tracker.py` demonstrated how complementary tools inspect different aspects of code health:
- **Semantic & Quality Analysis (Pylint):** Inspects the abstract syntax tree (AST) for logical design flaws, unused variables, unhandled resources, and PEP 8 conventions.
- **Security Vulnerability Scanning (Bandit):** Focuses specifically on security antipatterns, injection vectors, insecure functions, and Common Weakness Enumeration (CWE) classifications.
- **Style and Static Lint Checking (Flake8):** Verifies adherence to PEP 8 standards, identifying formatting anomalies, whitespace errors, and excess line lengths.

---

## 3. Tool Experience and Issue Identification on Applicant Tracking System

Each tool identified genuine issues in the original `recruitment_tracker.py`:

### Bandit (Security Assessment)
- **Dynamic SQL Query Construction (`B608` - Medium Severity, Medium Confidence):** In `addApplicant()`, f-string interpolation was used to build an `INSERT` statement, introducing a critical SQL injection risk (CWE-89) if applicant parameters contained untrusted input.
- **Insecure Function Usage (`B307` - Medium Severity, High Confidence):** In `shortlist()`, `eval(salary_rule)` was executed on arbitrary input, allowing remote code execution (CWE-78).
- **Suppression of Errors (`B110` - Low Severity, High Confidence):** In `updateStatus()`, `try...except Exception: pass` silently swallowed unexpected errors, masking database locks or query faults.

### Pylint (Code Quality & Correctness)
- **Inconsistent Returns (`R1710`):** `shortlist()` returned a list when applicants matched, but fell off the end returning `None` implicitly.
- **Resource Management (`R1732`, `W1514`):** In `exportReport()`, file operations were handled via bare `open()` without a context manager or explicit encoding.
- **Unused Local Variable (`W0612`):** `total_seen = len(rows)` was computed but never referenced.
- **Naming & Docstrings (`C0103`, `C0114`, `C0116`):** CamelCase function names violated PEP 8, and the module and functions lacked docstrings.
- **Baseline Score:** Pylint rated the original script at **4.47/10**.

### Flake8 (Style Consistency)
- **Line Length (`E501`):** Multiple lines exceeded 79 characters (up to 140 characters).
- **Unused Variable (`F841`):** Flagged `total_seen`.
- **Formatting Violations (`W291`, `E302`):** Trailing whitespace on line 15 and missing blank lines before top-level functions.

---

## 4. Interpreting Reports and Remediation Prioritization

Remediation was executed systematically based on issue severity:

### Step 1: Security Remediation (Bandit)
- **SQL Injection (`B608`):** Replaced string-formatted SQL with parameterized SQL queries using `?` placeholders (`INSERT INTO applicants VALUES (?, ?, ?, ?)`). This binds arguments as literal data values rather than executable SQL syntax.
- **Arbitrary Code Execution (`B307`):** Replaced `eval()` with an AST-based evaluator `_safe_eval_salary()` that only evaluates binary arithmetic operations (`+`, `-`, `*`, `/`) on numbers and strictly rejects arbitrary statements or module imports.
- **Exception Handling (`B110`):** Replaced `except Exception: pass` with targeted `sqlite3.Error` handling that surfaces actionable errors.

### Step 2: Quality & Design Remediation (Pylint)
- Wrapped file output in `with open(path, "w", encoding="utf-8") as file_handle:`.
- Added explicit `return None` in `shortlist()` when no candidates match.
- Removed unused variable `total_seen`.
- Renamed all functions to standard `snake_case` (`add_applicant`, `update_status`, `export_report`, `count_by_status`).
- Added modular `init_db()` and parameter injection for database connections.

### Step 3: Style & Cleanliness (Flake8)
- Cleaned trailing whitespace and enforced standard two-blank-line function spacing.
- Kept all lines strictly within 79 characters.
- Guarded `main()` with `if __name__ == "__main__":` to prevent execution upon module import.

---

## 5. Contributions to Code Quality, Security, and Maintainability

| Dimension | Original Version | Remediated Version |
| :--- | :--- | :--- |
| **Pylint Score** | `4.47 / 10` (21 messages) | **`10.00 / 10`** (0 warnings or conventions) |
| **Bandit Findings** | 3 issues (2 Medium, 1 Low) | **0 issues** ("No issues identified") |
| **Flake8 Violations** | 8 violations (`E501`, `F841`, `W291`, `E302`) | **0 violations** (Clean output) |
| **Database Safety** | Dynamic string interpolation in SQL | Parameterized SQL binding data values safely |
| **Rule Evaluation** | Insecure arbitrary `eval()` | Safe AST-based arithmetic whitelist evaluator |
| **File Resource Lifecycle** | Bare `open()` without `with` or encoding | Safe context-managed `with open(..., encoding="utf-8")` |
| **Import Behavior** | Executed demonstration on module import | Guarded with `if __name__ == "__main__":` |

Automated regression unit testing (`test_recruitment_tracker.py`) validated that all core functionalities were preserved and error conditions handled reliably.
