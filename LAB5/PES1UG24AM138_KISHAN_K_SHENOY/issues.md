# Lab 5: Static Code Analysis — Issues (recruitment_tracker.py)

- **Student:** Kishan K Shenoy
- **SRN:** PES1UG24AM138
- **Assigned Scenario:** 14 — Applicant Tracking System
- **Repository:** https://github.com/SETAPESU26/L5_14_recruitment_tracker
- **Tools:** Bandit (security), Pylint (quality, score before: 4.47/10), Flake8 (style)

Line numbers refer to the original file.

| Issue | Type | Line(s) | Description | Fix Approach |
| ----- | ---- | ------- | ----------- | ------------ |
| SQL injection (Bandit B608, Medium) | Security | 8 | `addApplicant` builds SQL statement via f-string interpolation, creating a severe SQL injection vulnerability (CWE-89) if applicant parameters contain crafted input. | Replaced string formatting with parameterized query binding: `active_conn.execute("INSERT INTO applicants ... VALUES (?, ?, ?, ?)", (name, role, expected_salary, status))`. |
| Arbitrary code execution via `eval` (Bandit B307 Medium, Pylint W0123) | Security | 14 | `shortlist` invokes `eval(salary_rule)` on an unvalidated string, allowing arbitrary code execution (CWE-78) via payload injection. | Implemented a dedicated whitelist-based AST parser `_safe_eval_salary()` that only evaluates binary arithmetic operations (`+`, `-`, `*`, `/`) on numbers and rejects everything else. |
| Insecure error suppression / `try...except pass` (Bandit B110 Low, Pylint W0718) | Security / Bug | 28–29 | `updateStatus` catches broad `Exception` and ignores it via `pass`, masking programming errors, schema issues, and database locks. | Caught specific `sqlite3.Error` and raised informative `RuntimeError` rather than silently swallowing exceptions. |
| Resource leak in file handling (Pylint R1732, W1514) | Resource Management | 32–35 | `exportReport` calls `open()` without a context manager (`with`) and without specifying character encoding, risking descriptor leaks and platform encoding issues. | Wrapped file access in `with open(path, "w", encoding="utf-8") as file_handle:`. |
| Inconsistent return statements (Pylint R1710) | Quality / Bug | 12–21 | `shortlist` returns `result` when candidates are found, but implicitly returns `None` via control flow fallthrough without an explicit statement. | Added explicit `return None` when no candidates match criteria. |
| Unused local variable (Pylint W0612, Flake8 F841) | Quality | 15 | `total_seen = len(rows)` is computed and assigned but never subsequently referenced. | Removed the unused variable assignment. |
| Non-conforming naming convention (Pylint C0103) | Style | 7, 24, 31, 38 | Function names `addApplicant`, `updateStatus`, `exportReport`, and `countByStatus` used camelCase instead of PEP 8 `snake_case`. | Renamed functions to `add_applicant`, `update_status`, `export_report`, and `count_by_status`. |
| Missing module and function docstrings (Pylint C0114, C0116) | Documentation | 1, 7, 12, 24, 31, 38, 42 | Module and all functions lacked docstrings explaining arguments, return types, and exceptions. | Added comprehensive docstrings adhering to Google/PEP 257 standards. |
| Excess line lengths (Pylint C0301, Flake8 E501) | Style | 4, 8, 13, 26, 39 | Lines exceeded 79 characters (up to 140 characters in SQL statements). | Reformatted and split strings and statements across multiple lines. |
| Trailing whitespace & blank line spacing (Pylint C0303, Flake8 W291, E302) | Style | 15, 31 | Line 15 contained trailing whitespace and functions lacked standard two blank lines separation. | Cleaned whitespace and enforced two blank lines between top-level definitions. |
| Execution upon module import | Architecture | 49 | `main()` was called unconditionally at the module root, executing demo operations whenever imported by tests. | Guarded execution with `if __name__ == "__main__":`. |

---

## Tool Assessment Results

| Tool | Baseline Before | Remediated After |
| ---- | --------------- | ---------------- |
| **Bandit** | 3 issues (2 Medium, 1 Low) | **0 issues** ("No issues identified") |
| **Pylint** | **4.47 / 10** | **10.00 / 10** |
| **Flake8** | 8 violations (`E501`, `F841`, `W291`, `E302`) | **0 violations** (Clean output) |

The program maintains exact functional equivalence with the original, returning `['Nina']` and `2 in interview`, while passing all automated regression unit tests.
