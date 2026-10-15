"""Alembic environment: migrate the database named by DATABASE_URL, or by `sqlalchemy.url` when a caller sets it (tests)."""

from alembic import context
from sqlalchemy import create_engine, pool

from anisotropy_api.records import Base
from anisotropy_api.settings import database_url_for_migrations

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or database_url_for_migrations()
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline SQL-script mode is not used here; run the migrations against a database.")
run_migrations_online()
