"""Add referenced_player_ids column to app.chat_messages.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20 00:00:00.000000

Inherits the `app` branch label from revision 0003 through 0004 and does not
re-declare branch_labels. Stores only player IDs referenced by an assistant
message so session restore can rehydrate portraits, club crests, league logos
and flags without persisting denormalized URLs.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE app.chat_messages
            ADD COLUMN referenced_player_ids INTEGER[] NOT NULL DEFAULT '{}';
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE app.chat_messages DROP COLUMN IF EXISTS referenced_player_ids;")
