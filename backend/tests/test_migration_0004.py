"""Static checks on migration 0004 (report provenance).

Input: the migration source at the repository root.
Output: assertions on the order and content of the executed SQL statements.
Responsibility: the migration must normalise legacy report_type values before
constraining them (a legacy row would otherwise abort the deploy) and must
constrain the `source` vocabulary the schema documents.
"""

from __future__ import annotations

import ast
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0004_report_provenance.py"
)


def _executed_statements() -> list[str]:
    """Return every SQL string the migration executes, in execution order."""
    tree = ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))
    statements: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "execute"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        value = node.args[0].value
        if isinstance(value, str):
            statements.append(value)
    return statements


def test_report_type_is_normalised_before_the_check_constraint() -> None:
    """Legacy non-scouting rows are rewritten, not treated as a fatal error."""
    statements = _executed_statements()
    normalise = next(
        (
            i
            for i, sql in enumerate(statements)
            if "UPDATE app.reports" in sql and "report_type = 'scouting'" in sql
        ),
        None,
    )
    constraint = next(
        (
            i
            for i, sql in enumerate(statements)
            if "ADD CONSTRAINT reports_report_type_check" in sql
        ),
        None,
    )
    assert normalise is not None, "no statement normalises app.reports.report_type"
    assert constraint is not None, "no CHECK constraint on app.reports.report_type"
    assert normalise < constraint, "report_type must be normalised before the CHECK is added"


def test_migration_does_not_abort_on_legacy_report_types() -> None:
    """The migration reports the normalised rows instead of raising."""
    statements = _executed_statements()
    assert not any("RAISE EXCEPTION" in sql for sql in statements)
    assert any("RAISE NOTICE" in sql for sql in statements)


def test_source_vocabulary_is_constrained() -> None:
    """The `source` column only accepts the two documented generators."""
    statements = _executed_statements()
    assert any(
        "ADD CONSTRAINT reports_source_check" in sql and "IN ('llm','deterministic')" in sql
        for sql in statements
    )


def test_downgrade_drops_both_check_constraints() -> None:
    """The rollback removes the constraints the migration adds."""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "DROP CONSTRAINT IF EXISTS reports_report_type_check" in source
    assert "DROP CONSTRAINT IF EXISTS reports_source_check" in source
