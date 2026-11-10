"""Add report provenance columns and narrow the report_type vocabulary.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09 00:00:00.000000

The `app` branch label is inherited from revision 0003 through `down_revision`;
it must not be re-declared here. Alembic requires branch labels to be globally
unique, so declaring it again raises `RevisionError: Branch name 'app' ...
already used by revision 0003` and breaks every alembic command.

Legacy rows are normalised rather than rejected: before this revision the API
accepted any `report_type` string and the generator ignored it, so a row with a
non-'scouting' value is a scouting report under a wrong cache key. Aborting the
migration on such a row would break the whole deploy, because the backend
service waits for a successful migration before it starts.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. provenance columns
    # source records which generator produced the report ('llm' or 'deterministic').
    # llm_model and prompt_version carry the model id and the prompt/sampling
    # configuration; both are NULL for a deterministic report.
    # The NOT NULL DEFAULT on source is applied by PostgreSQL to the existing
    # rows atomically with the ADD COLUMN, so no separate backfill is needed:
    # every report produced so far came from the LLM path.
    op.execute(
        """
        ALTER TABLE app.reports
            ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'llm';
        """
    )
    op.execute(
        """
        ALTER TABLE app.reports
            ADD COLUMN llm_model VARCHAR(128) NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE app.reports
            ADD COLUMN prompt_version VARCHAR(32) NULL;
        """
    )

    # 2. narrow report_type to the single vocabulary the product has.
    # There is exactly one report generator (backend generate_report) and exactly
    # one report surface, so 'scouting' is the only meaningful value. The value
    # is used only as a cache key: the generator ignores it. A wider vocabulary
    # would let a request for a non-existent report type silently store a
    # scouting report under a misleading cache key.
    # Legacy rows are normalised, not rejected: before this revision
    # ReportGenerateRequest.report_type was a free string that the generator
    # ignored, so a row with any other value is a scouting report filed under a
    # wrong key, not corrupt data. Rewriting it to 'scouting' is lossless and
    # keeps the deploy from aborting on the migrate service (the backend waits
    # for a successful migration before it starts).
    # The constraint name follows the table_column_check convention used by the
    # unnamed inline CHECK constraints of 0001/0002/0003.
    op.execute(
        """
        DO $$
        DECLARE
            normalised_count INTEGER;
        BEGIN
            UPDATE app.reports
            SET report_type = 'scouting'
            WHERE report_type <> 'scouting';
            GET DIAGNOSTICS normalised_count = ROW_COUNT;
            IF normalised_count > 0 THEN
                RAISE NOTICE
                    'Normalised % app.reports row(s) with a report_type outside ''scouting''',
                    normalised_count;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE app.reports
            ADD CONSTRAINT reports_report_type_check CHECK (report_type IN ('scouting'));
        """
    )

    # 3. narrow source to the two generators the backend knows: the LLM path
    # and the deterministic fallback. The column is NOT NULL and defaulted to
    # 'llm' by the ADD COLUMN above, so existing rows already satisfy it.
    op.execute(
        """
        ALTER TABLE app.reports
            ADD CONSTRAINT reports_source_check CHECK (source IN ('llm','deterministic'));
        """
    )

    # No new table is created, so the GRANTs of 0003 on app.reports and on the
    # app schema already cover the new columns; no extra grant is needed.


def downgrade() -> None:
    op.execute("ALTER TABLE app.reports DROP CONSTRAINT IF EXISTS reports_source_check;")
    op.execute("ALTER TABLE app.reports DROP CONSTRAINT IF EXISTS reports_report_type_check;")
    op.execute("ALTER TABLE app.reports DROP COLUMN IF EXISTS prompt_version;")
    op.execute("ALTER TABLE app.reports DROP COLUMN IF EXISTS llm_model;")
    op.execute("ALTER TABLE app.reports DROP COLUMN IF EXISTS source;")
