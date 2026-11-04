import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = None


def get_url() -> str:
    """Resolve database URL from environment variables or config."""
    admin_url = os.environ.get("DELPHOS_ADMIN_DATABASE_URL")
    if admin_url:
        return admin_url

    # Check postgres superuser / admin credentials
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres_secret")
    db_host = os.environ.get("DELPHOS_DB_HOST", "localhost")
    db_port = os.environ.get("DELPHOS_DB_PORT", "5432")
    db_name = os.environ.get("DELPHOS_DB_NAME", os.environ.get("POSTGRES_DB", "delphos"))

    if pg_user and pg_password:
        return f"postgresql+psycopg://{pg_user}:{pg_password}@{db_host}:{db_port}/{db_name}"

    db_url = os.environ.get("DELPHOS_DATABASE_URL")
    if db_url:
        return db_url

    return config.get_main_option("sqlalchemy.url", "postgresql+psycopg://postgres:postgres_secret@localhost:5432/delphos")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

