"""Unit tests for recruitment_tracker module."""

import os
import pytest
from recruitment_tracker import (
    init_db,
    add_applicant,
    shortlist,
    update_status,
    export_report,
    count_by_status,
    _safe_eval_salary,
)


@pytest.fixture
def test_db():
    """Create a fresh isolated database connection for each test."""
    return init_db()


def test_add_and_count(test_db):
    """Test inserting applicants and counting by status."""
    add_applicant("Alice", "developer", 800000, "applied", db_conn=test_db)
    add_applicant("Bob", "developer", 900000, "interview", db_conn=test_db)
    assert count_by_status("applied", db_conn=test_db) == 1
    assert count_by_status("interview", db_conn=test_db) == 1
    assert count_by_status("hired", db_conn=test_db) == 0


def test_shortlist_filter(test_db):
    """Test candidate shortlisting based on role and salary rule."""
    add_applicant("Nina", "analyst", 600000, "applied", db_conn=test_db)
    add_applicant("Omar", "analyst", 750000, "applied", db_conn=test_db)
    add_applicant("Priya", "developer", 700000, "applied", db_conn=test_db)

    # 500000 + 150000 = 650000 limit -> only Nina qualifies
    shortlisted = shortlist("analyst", "500000 + 150000", db_conn=test_db)
    assert shortlisted == ["Nina"]


def test_shortlist_none_found(test_db):
    """Test shortlisting when no candidate meets the budget."""
    add_applicant("Sam", "manager", 1200000, "applied", db_conn=test_db)
    assert shortlist("manager", "1000000", db_conn=test_db) is None


def test_update_status(test_db):
    """Test updating status of candidate."""
    add_applicant("Nina", "analyst", 600000, "applied", db_conn=test_db)
    assert count_by_status("applied", db_conn=test_db) == 1
    update_status(1, "interview", db_conn=test_db)
    assert count_by_status("applied", db_conn=test_db) == 0
    assert count_by_status("interview", db_conn=test_db) == 1


def test_export_report(test_db, tmp_path):
    """Test CSV report generation."""
    add_applicant("Nina", "analyst", 600000, "applied", db_conn=test_db)
    add_applicant("Omar", "analyst", 750000, "interview", db_conn=test_db)

    report_file = tmp_path / "test_report.csv"
    export_report(str(report_file), db_conn=test_db)

    assert os.path.exists(report_file)
    content = report_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 2
    assert "Nina,analyst,applied" in content[0]
    assert "Omar,analyst,interview" in content[1]


def test_safe_eval_rejection():
    """Verify safe eval prevents arbitrary execution and dangerous syntax."""
    assert _safe_eval_salary("500000 + 150000") == 650000
    assert _safe_eval_salary("1000000 - 200000") == 800000
    assert _safe_eval_salary("200000 * 3") == 600000

    with pytest.raises(Exception):
        _safe_eval_salary("__import__('os').system('ls')")
