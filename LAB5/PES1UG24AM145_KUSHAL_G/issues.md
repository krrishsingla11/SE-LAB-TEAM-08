# Lab 5: Static Code Analysis — Issues (`wildlife_sightings.py`)

- **Student:** Kushal G
- **SRN:** PES1UG24AM145
- **Scenario:** 21 — Wildlife Sightings
- **Repository:** https://github.com/SETAPESU26/L5_21_wildlife_sightings
- **Tools:** Bandit (security), Pylint (code quality & bugs), Flake8 (PEP 8 style)

*Note: Line numbers refer to the original untouched file.*

## Identified Issues and Fixes

| Issue | Type | Line(s) | Description | Fix Approach |
| :--- | :--- | :--- | :--- | :--- |
| **SQL Injection Vector** (Bandit `B608`, Medium) | Security | 9 | `logSighting` constructs SQL via `.format()`, allowing SQL injection payloads to alter SQL syntax. | Replaced string interpolation with parameterized SQL: `conn.execute("INSERT INTO sightings (species, zone, count) VALUES (?, ?, ?)", (species, zone, count))`. |
| **Weak MD5 Hash Usage** (Bandit `B324`, High) | Security | 15 | `observerId` computes MD5 hash, which is cryptographically broken and prone to collision attacks. | Replaced MD5 with SHA-256 (`hashlib.sha256(observer.encode("utf-8")).hexdigest()[:6]`) and documented that it serves as a deterministic short identifier, not authentication. |
| **Use of Assert Statement** (Bandit `B101`, Low) | Security / Reliability | 36 | `assert len(totals) == 3` is stripped in optimized Python runs (`-O` / `-OO`), bypassing verification. | Replaced assert with an explicit runtime exception: `if len(totals) != 3: raise RuntimeError(...)`. |
| **Mutable Default Argument** (Pylint `W0102`) | Bug Risk | 8 | `extras={}` creates a mutable dictionary evaluated once at definition time and shared across subsequent calls. | Changed default parameter to `extras=None` and initialized `extras = {}` inside the function. |
| **Outer Scope Variable Shadowing** (Pylint `W0621`) | Scope / Quality | 8, 18, 26 | Parameter name `conn` shadows module-level global variable `conn` declared on Line 4. | Removed global `conn` variable; encapsulated schema creation in `init_db()` and managed connection locally in `main()`. |
| **Unnecessary Else After Return** (Pylint `R1705`) | Refactoring / Style | 20–23 | `zoneSummary` had `if row[0] is None: return 0 else: return row[0]`, where `else` is redundant after `return`. | Removed redundant `else` and simplified control flow: `if row is None or row[0] is None: return 0; return row[0]`. |
| **CamelCase Function Names** (Pylint `C0103`) | Style | 8, 14, 18 | `logSighting`, `observerId`, and `zoneSummary` violate PEP 8 `snake_case` naming conventions. | Renamed functions to `log_sighting`, `observer_id`, and `zone_summary` and updated all caller references. |
| **Missing Docstrings** (Pylint `C0114`, `C0116`) | Documentation | 1, 8, 14, 18, 26, 32 | Module and functions lack docstrings explaining their purpose, parameters, and return types. | Added descriptive PEP 257 docstrings to module and all functions. |
| **Ambiguous Variable Name** (Flake8 `E741`) | Style | 28 | Single-letter variable `l` in `rarest` is visually ambiguous and easily confused with numeral `1` or uppercase `I`. | Renamed variable `l` to `rarest_species`. |
| **Missing Whitespace Around Operator** (Flake8 `E225`) | Style | 28 | `l=min(...)` lacks required whitespace around assignment operator `=`. | Added spacing around operator: `rarest_species = min(...)`. |
| **Line Length Limit Exceeded** (Flake8 `E501`, Pylint `C0301`) | Style | 5, 9, 19, 27 | Lines exceeded PEP 8 79-character limit (up to 117 characters on Line 9). | Wrapped multi-line SQL queries, parameters, and statements within 79 characters. |
| **Top-Level Code Execution on Import** (Manual Finding) | Architecture / Robustness | 40 | `main()` executed unconditionally when imported as a library module. | Enclosed script execution in standard `if __name__ == "__main__":` guard. |
| **Unclosed SQLite Connection Resource Leak** (Manual Finding) | Resource Management | 4 | Database connection `conn` was never explicitly closed. | Added `try...finally` block in `main()` with explicit `conn.close()` to ensure proper cleanup. |
| **Empty Table Exception in `rarest()`** (Manual Finding) | Robustness | 28 | Calling `rarest()` on an empty database raised an unhandled `ValueError: min() arg is an empty sequence`. | Added guard `if not rows: return None` before evaluating `min()`. |

---

## Results Summary

| Tool | Before Remediation | After Remediation | Status |
| :--- | :--- | :--- | :--- |
| **Bandit** | 3 issues (1 High, 1 Medium, 1 Low) | **0 issues** ("No issues identified") | Passed |
| **Pylint** | 3.46 / 10 (17 messages) | **10.00 / 10** | Passed (Target > 9.5) |
| **Flake8** | 6 violations | **0 violations** (Empty output) | Passed |

---

## Program Output Verification

- **Before:** `5455c3 25 Leopard` (using MD5 for observer ID)
- **After:** `e753d3 25 Leopard` (using SHA-256 for observer ID)
- **Functional Integrity:** Zone counts (`25`), rarity assessment (`Leopard`), and species total validations are 100% preserved.
