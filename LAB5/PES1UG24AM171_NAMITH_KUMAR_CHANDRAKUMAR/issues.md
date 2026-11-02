# Lab 5: Static Code Analysis — Issues (`hospital_patient_system.py`)

- **Student:** Namith Kumar Chandrakumar
- **SRN:** PES1UG24AM171
- **Scenario:** 46 — Hospital Patient Management System
- **Repository:** https://github.com/SETAPESU26/L5_46_hospital_patient_management_system
- **Tools:** Bandit (security), Pylint (code quality & bugs), Flake8 (PEP 8 style)

*Note: Line numbers refer to the original untouched file.*

## Identified Issues and Fixes

| Issue | Type | Line(s) | Description | Fix Approach |
| :--- | :--- | :--- | :--- | :--- |
| **Command Injection via Shell** (Bandit `B605`, High) | Security | 56 | `os.system("echo Patient ledger exported to: " + filename)` starts a shell process with string concatenation, exposing the system to command injection vulnerabilities. | Replaced `os.system` entirely with Python's built-in `print(f"Patient ledger exported to: {filename}")` and removed the insecure `os` import. |
| **Weak MD5 Hash Usage** (Bandit `B324`, High) | Security | 45 | `hashlib.md5(p_id.encode()).hexdigest()` uses MD5, a cryptographically broken hashing algorithm vulnerable to collision attacks. | Migrated to SHA-256 (`hashlib.sha256(p_id.encode("utf-8")).hexdigest()`), providing robust collision resistance for patient record hashing. |
| **Insecure Dynamic Code Execution via `eval`** (Bandit `B307`, Medium; Pylint `W0123`) | Security / Code Execution | 40 | `total = eval(formula_expr)` executes arbitrary code passed as a string, presenting a severe arbitrary code execution vulnerability. | Refactored `calculate_treatment_cost` to accept a numeric `multiplier` parameter and perform direct arithmetic computation (`float(base_bill) * float(multiplier)`), eliminating `eval()`. |
| **Insecure Pseudo-Random Generator for Tokens** (Bandit `B311`, Low) | Security | 49 | `random.randint(1000, 9999)` uses Mersenne Twister PRNG, which is predictable and unsuitable for security-sensitive tokens. | Replaced `random` with Python's standard `secrets` cryptographic module (`secrets.randbelow(9000) + 1000`). |
| **Bare `except` & Silent Exception Suppression** (Bandit `B110`, Low; Pylint `W0702`; Flake8 `E722`) | Bug Risk / Exception Handling | 24–25 | A bare `except: pass` catches and suppresses all exceptions, including `KeyboardInterrupt` and `SystemExit`, masking unintended errors. | Specified exact expected exception `except KeyError:` to safely handle only missing patient records. |
| **Mutable Default Argument** (Pylint `W0102`) | Bug Risk | 13 | `intake_log=[]` defines a mutable list evaluated once at function definition time, inadvertently sharing state across subsequent calls without explicit arguments. | Changed parameter default to `intake_log=None` and initialized `intake_log = []` inside the function body. |
| **Non-standard CamelCase Function Name** (Pylint `C0103`) | Style / Convention | 13 | `admitPatient` violates PEP 8 `snake_case` naming conventions for functions. | Renamed function to `admit_patient` and updated all callers. |
| **Unclosed File & Missing Encoding** (Pylint `R1732`, `W1514`) | Resource Leak / Portability | 53–55 | File opened with `f = open(filename, "w")` without a context manager or explicit encoding, risking descriptor leakage on exceptions and cross-platform encoding bugs. | Refactored to safe context manager `with open(filename, "w", encoding="utf-8") as file:`. |
| **Outer Scope Variable Shadowing** (Pylint `W0621`) | Scope / Quality | 59 | Parameter `patient_records` in `get_ward_summary` shadowed module-level global variable `patient_records`. | Renamed global dictionary to uppercase constant `PATIENT_RECORDS` and parameter to `records`. |
| **Unused Variables and Imports** (Pylint `W0611`, `W0612`; Flake8 `F401`, `F841`) | Dead Code | 4, 29, 39, 61 | Unused import `math`, unused variables `bed_charge`, `base_bill` (pre-eval), and loop counter `p`. | Removed `import math`, unused variables, and refactored loop to idiomatic `sum(1 for details in records.values() if details["is_admitted"])`. |
| **PEP 8 Line Length Violations** (Flake8 `E501`) | Style | 7, 8, 9, 16, 72 | Multiple lines exceeded the PEP 8 79-character limit (up to 93 characters). | Split dictionary entries, function signatures, and print statements across multiple lines conforming to 79 characters. |
| **Missing Module & Function Docstrings** (Pylint `C0114`, `C0116`) | Documentation | 1, 13, 21, 28, 38, 44, 48, 52, 59, 67 | Missing docstrings explaining module and function contracts, parameters, and return types. | Added comprehensive PEP 257 docstrings for module and all functions. |
| **Direct Import Execution Without Guard** (Best Practice) | Architecture | 80 | `main()` executed directly at top-level on import. | Protected execution with `if __name__ == "__main__": main()`. |

---

## Results Summary

| Tool | Before Remediation | After Remediation | Status |
| :--- | :--- | :--- | :--- |
| **Bandit** | 5 issues (2 High, 1 Medium, 2 Low) | **0 issues** ("No issues identified") | Passed |
| **Pylint** | 5.19 / 10 (21 messages) | **10.00 / 10** | Passed (Target > 9.5) |
| **Flake8** | 11 violations | **0 violations** (Empty output) | Passed |

---

## Program Output Verification

- **Before:**
  ```text
  Patient ledger exported to: patient_records.txt
  Is P103 admitted: True
  Cost calculated: 1344.0000000000002
  Patient Hash: fdd6dec2aa5db13215f10e2589bb24cb
  Ward Token: 6310
  Active admits: 2
  Access key: HOSPITAL_NURSE_MASTER_KEY_2026
  ```
- **After:**
  ```text
  Is P103 admitted: True
  Cost calculated: 1344.0000000000002
  Patient Hash: 063b8ff279d9e5d56585b4bc8cee04e3f29907409f86cfba9da3fa0794e62710
  Ward Token: 1897
  Patient ledger exported to: patient_records.txt
  Active admits: 2
  Access key: HOSPITAL_NURSE_MASTER_KEY_2026
  ```
- **Functional Integrity:** All functional requirements (admission tracking, patient status checks, bill calculation, active admit count, and ledger export) remain intact and fully verified.
