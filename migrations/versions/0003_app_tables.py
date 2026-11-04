"""Create app tables, indexes, and constraints.

Revision ID: 0003
Revises: 0001
Create Date: 2026-11-04 00:02:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("app",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. shortlists
    op.execute(
        """
        CREATE TABLE app.shortlists (
            id SERIAL PRIMARY KEY,
            player_id INTEGER NOT NULL UNIQUE,
            notes TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 2. reports
    op.execute(
        """
        CREATE TABLE app.reports (
            id SERIAL PRIMARY KEY,
            player_id INTEGER NOT NULL,
            model_run_id VARCHAR(64) NOT NULL,
            report_type VARCHAR(64) NOT NULL DEFAULT 'scouting',
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_reports_player ON app.reports (player_id, model_run_id);
        """
    )

    # 3. chat_sessions
    op.execute(
        """
        CREATE TABLE app.chat_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(256) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 4. chat_messages
    op.execute(
        """
        CREATE TABLE app.chat_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES app.chat_sessions(id) ON DELETE CASCADE,
            role VARCHAR(32) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            model_run_id VARCHAR(64) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_chat_messages_session ON app.chat_messages (session_id, created_at);
        """
    )

    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO delphos_app_user;")
    op.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO delphos_app_user;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.chat_messages CASCADE;")
    op.execute("DROP TABLE IF EXISTS app.chat_sessions CASCADE;")
    op.execute("DROP TABLE IF EXISTS app.reports CASCADE;")
    op.execute("DROP TABLE IF EXISTS app.shortlists CASCADE;")

