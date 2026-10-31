# Lab 5: Static Code Analysis - Issues (society_dues.py)

Tools: Bandit (security), Pylint (quality, before score 5.81/10), Flake8 (style).
Line numbers refer to the original file.

| Issue | Type | Line(s) | Description | Fix Approach |
| ----- | ---- | ------- | ----------- | ------------ |
| SQL injection (Bandit B608, Medium) | Security | 9 | `addDue` builds the INSERT with an f-string, so a flat or month value like `x'); DROP TABLE dues;--` would be run as SQL. | Use a parameterised query: `conn.execute("INSERT INTO dues VALUES (?, ?, ?, 0)", (flat, month, amount))`. |
| Use of `eval` (Bandit B307 Medium, Pylint W0123) | Security | 21 | `penalty` runs `eval(rule)` on a string, so any Python code in `rule` would be executed. | Parse the rule with `ast.parse(rule, mode="eval")` and evaluate only numbers and `+ - * /` with a small whitelist-based `_safe_eval`. Anything else returns a fee of 0. |
| Hardcoded password (Bandit B105, Low) | Security | 5 | `TREASURER_PASSWORD = "flat#101"` keeps a secret in the source code and in Git history. | Read it from the environment: `os.environ.get("TREASURER_PASSWORD", "")`. |
| Mutable default argument (Pylint W0102) | Bug | 8 | `history=[]` is created once and shared by every call, so history from different calls gets mixed together. | Change the default to `None` and create a new list inside the function. |
| Overly broad exception (Pylint W0718) | Bug | 22 | `except Exception` hides every error, including programming mistakes. | Catch only the expected errors: `SyntaxError, ValueError, TypeError, ZeroDivisionError, RecursionError`. |
| Inconsistent return (Pylint R1710) | Bug | 12-17 | `collect` returns a value when a row is found and nothing otherwise. | Add an explicit `return None` at the end of the function. |
| Comparison to `None` with `!=` (Pylint C0121, Flake8 E711) | Style / Bug | 29 | `rows != None` is the wrong way to compare with None, and `fetchall()` never returns None anyway. | Remove the check and return `[r[0] for r in rows]` (an empty list is returned automatically if there are no rows). |
| Function name `addDue` (Pylint C0103) | Style | 8 | CamelCase does not follow the snake_case naming convention. | Rename to `add_due` and update the calls in `main`. |
| Missing docstrings (Pylint C0114, C0116) | Style | 1, 8, 12, 19, 27, 34 | Module and functions have no documentation. | Add a short docstring to the module and to every function. |
| Lines too long (Pylint C0301, Flake8 E501) | Style | 4, 13, 15 | Lines are 87, 104 and 92 characters long (limit 79 for Flake8). | Split long strings and calls across several lines, using a `query` variable for the SELECT. |
| Missing blank lines (Flake8 E302) | Style | 12 | `collect` is not separated from the previous function by 2 blank lines. | Add 2 blank lines between top-level functions. |
| `main()` runs on import | Design | 41 | `main()` is called at module level, so the demo runs whenever the file is imported. | Wrap it in `if __name__ == "__main__":`. |

## Results

| Tool | Before | After |
| ---- | ------ | ----- |
| Bandit | 3 issues (1 Low, 2 Medium) | 0 ("No issues identified") |
| Pylint | 5.81/10 | 10.00/10 |
| Flake8 | 5 issues | 0 (empty report) |

Program output before and after the changes is identical (`2500`, `100`, `['A-102']`).
