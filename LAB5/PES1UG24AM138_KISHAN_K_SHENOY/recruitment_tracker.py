"""Applicant Tracking System module for managing recruitment workflows.

Provides database creation, candidate insertion, rule-based shortlisting,
status updates, summary queries, and CSV report export.
"""

import ast
import operator
import sqlite3

# Supported binary arithmetic operators for safe expression evaluation
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _safe_eval_salary(expr_str):
    """Safely evaluate an arithmetic expression for salary limits.

    Only simple mathematical operations (+, -, *, /) on numbers are allowed.
    """
    def _eval_node(node):
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(
            node.value, (int, float)
        ):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            return _OPERATORS[type(node.op)](left, right)
        raise ValueError(f"Unsupported expression element: {type(node)}")

    parsed = ast.parse(expr_str.strip(), mode="eval")
    return int(_eval_node(parsed))


def init_db():
    """Initialize an in-memory SQLite database with applicants table."""
    connection = sqlite3.connect(":memory:")
    query = (
        "CREATE TABLE applicants ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT, "
        "role TEXT, "
        "expected_salary INTEGER, "
        "status TEXT)"
    )
    connection.execute(query)
    connection.commit()
    return connection


# Default module-level connection for interactive and legacy use
conn = init_db()


def add_applicant(name, role, expected_salary, status="applied", db_conn=None):
    """Add a new job applicant using safe parameterized query binding."""
    active_conn = db_conn if db_conn is not None else conn
    query = (
        "INSERT INTO applicants (name, role, expected_salary, status) "
        "VALUES (?, ?, ?, ?)"
    )
    active_conn.execute(query, (name, role, expected_salary, status))
    active_conn.commit()


def shortlist(role, salary_rule, db_conn=None):
    """Shortlist candidates matching role and budget evaluated safely."""
    active_conn = db_conn if db_conn is not None else conn
    query = (
        "SELECT name, expected_salary FROM applicants "
        "WHERE role = ?"
    )
    rows = active_conn.execute(query, (role,)).fetchall()
    limit = _safe_eval_salary(salary_rule)
    result = [name for name, salary in rows if salary <= limit]
    if result:
        return result
    return None


def update_status(applicant_id, status, db_conn=None):
    """Update applicant hiring status safely."""
    active_conn = db_conn if db_conn is not None else conn
    query = "UPDATE applicants SET status = ? WHERE id = ?"
    try:
        active_conn.execute(query, (status, applicant_id))
        active_conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Database error updating status: {exc}") from exc


def export_report(path, db_conn=None):
    """Export applicant report into a UTF-8 encoded CSV file."""
    active_conn = db_conn if db_conn is not None else conn
    query = "SELECT name, role, status FROM applicants"
    with open(path, "w", encoding="utf-8") as file_handle:
        for row in active_conn.execute(query):
            file_handle.write(",".join(row) + "\n")


def count_by_status(status, db_conn=None):
    """Count number of applicants with a specific status."""
    active_conn = db_conn if db_conn is not None else conn
    query = "SELECT COUNT(*) FROM applicants WHERE status = ?"
    cursor = active_conn.execute(query, (status,))
    row = cursor.fetchone()
    return row[0] if row else 0


def main():
    """Demonstrate applicant tracking operations."""
    add_applicant("Nina", "analyst", 600000)
    add_applicant("Omar", "analyst", 750000, "interview")
    add_applicant("Priya", "developer", 900000)
    update_status(1, "interview")
    print(shortlist("analyst", "500000 + 150000"))
    export_report("applicants_report.csv")
    print(count_by_status("interview"), "in interview")


if __name__ == "__main__":
    main()
