"""Apartment society maintenance dues ledger."""
import ast
import operator
import os
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute(
    "CREATE TABLE dues "
    "(flat TEXT, month TEXT, amount INTEGER, paid INTEGER)"
)
TREASURER_PASSWORD = os.environ.get("TREASURER_PASSWORD", "")

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _safe_eval(node):
    """Evaluate a parsed arithmetic expression without using eval()."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](
            _safe_eval(node.left), _safe_eval(node.right)
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    raise ValueError("unsupported expression")


def add_due(flat, month, amount, history=None):
    """Bill a flat for a month and record it in the history list."""
    if history is None:
        history = []
    conn.execute(
        "INSERT INTO dues VALUES (?, ?, ?, 0)", (flat, month, amount)
    )
    history.append((flat, month))
    return history


def collect(flat, month):
    """Mark a due as paid and return the amount, or None if not found."""
    query = "SELECT amount FROM dues WHERE flat = ? AND month = ?"
    row = conn.execute(query, (flat, month)).fetchone()
    if row:
        conn.execute(
            "UPDATE dues SET paid = 1 WHERE flat = ? AND month = ?",
            (flat, month),
        )
        return row[0]
    return None


def penalty(rule):
    """Return the late fee for an arithmetic rule such as '50 * 2'."""
    try:
        late_fee = _safe_eval(ast.parse(rule, mode="eval"))
    except (
        SyntaxError, ValueError, TypeError, ZeroDivisionError, RecursionError
    ):
        late_fee = 0
    return late_fee


def pending():
    """Return the list of flats that still have unpaid dues."""
    rows = conn.execute("SELECT flat FROM dues WHERE paid = 0").fetchall()
    return [r[0] for r in rows]


def main():
    """Run a short demonstration of the ledger."""
    add_due("A-101", "Oct", 2500)
    add_due("A-102", "Oct", 2500)
    print(collect("A-101", "Oct"))
    print(penalty("50 * 2"))
    print(pending())


if __name__ == "__main__":
    main()
