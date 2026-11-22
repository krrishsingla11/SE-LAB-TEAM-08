# Lab 5: Static Code Analysis — Applicant Tracking System

## Student Details
- **Student Name**: Kishan K Shenoy
- **SRN**: PES1UG24AM138
- **Assigned Scenario**: Scenario 14 — Applicant Tracking System
- **Repository**: `SETAPESU26/L5_14_recruitment_tracker`
- **Application Module**: `recruitment_tracker.py`

---

## Deliverables Summary

1. `recruitment_tracker.py`: Remediated Python module achieving **10.00/10** Pylint score, 0 Bandit issues, and 0 Flake8 violations.
2. `issues.md`: Detailed documentation of all identified quality, security, and style issues with fix approaches.
3. `reflection.md`: Structured personal reflection addressing the official Lab 5 learning outcomes.
4. `test_recruitment_tracker.py`: Automated pytest suite verifying functionality, edge cases, and safe arithmetic evaluation.
5. Analysis reports:
   - `pylint_report_before.txt` & `pylint_report_after.txt`
   - `bandit_report_before.txt` & `bandit_report_after.txt`
   - `flake8_report_before.txt` & `flake8_report_after.txt`

---

## Commands to Run Analysis Tools

### 1. Pylint (Code Quality & Correctness)
```bash
pylint recruitment_tracker.py
```

### 2. Bandit (Security Assessment)
```bash
bandit -r recruitment_tracker.py
```

### 3. Flake8 (Style Consistency)
```bash
flake8 recruitment_tracker.py
```

### 4. Automated Unit Testing
```bash
pytest -v test_recruitment_tracker.py
```
