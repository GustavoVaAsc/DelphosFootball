"""Bootstrap roles and schemas for DelphosFootball.

Revision ID: 0001
Revises: None
Create Date: 2026-11-04 02:30:00.000000
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pub_pw = os.environ.get("DELPHOS_DB_PASSWORD", "delphos_ml_publisher_secret")
    app_pw = os.environ.get("DELPHOS_APP_DB_PASSWORD", "delphos_app_user_secret")
    pub_pw_escaped = pub_pw.replace("'", "''")
    app_pw_escaped = app_pw.replace("'", "''")

    # 1. Create database roles if they do not exist
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'delphos_ml_publisher') THEN
                EXECUTE format('CREATE ROLE delphos_ml_publisher WITH LOGIN PASSWORD %L', '{pub_pw_escaped}');
            END IF;
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'delphos_app_user') THEN
                EXECUTE format('CREATE ROLE delphos_app_user WITH LOGIN PASSWORD %L', '{app_pw_escaped}');
            END IF;
        END
        $$;
        """
    )

    # 2. Create schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION delphos_ml_publisher;")
    op.execute("CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION delphos_app_user;")

    # 3. Grants for delphos_ml_publisher (writes analytics only)
    op.execute("GRANT USAGE, CREATE ON SCHEMA analytics TO delphos_ml_publisher;")
    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO delphos_ml_publisher;")
    op.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA analytics TO delphos_ml_publisher;")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON TABLES TO delphos_ml_publisher;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON SEQUENCES TO delphos_ml_publisher;"
    )

    # 4. Grants for delphos_app_user (reads analytics, owns app)
    op.execute("GRANT USAGE ON SCHEMA analytics TO delphos_app_user;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO delphos_app_user;")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO delphos_app_user;"
    )

    op.execute("GRANT USAGE, CREATE ON SCHEMA app TO delphos_app_user;")
    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO delphos_app_user;")
    op.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO delphos_app_user;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON TABLES TO delphos_app_user;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON SEQUENCES TO delphos_app_user;")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS app CASCADE;")
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE;")
    op.execute("DROP OWNED BY delphos_app_user CASCADE;")
    op.execute("DROP ROLE IF EXISTS delphos_app_user;")
    op.execute("DROP OWNED BY delphos_ml_publisher CASCADE;")
    op.execute("DROP ROLE IF EXISTS delphos_ml_publisher;")
