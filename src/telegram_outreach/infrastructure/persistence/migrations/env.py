"""Alembic environment."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from telegram_outreach.config.settings import get_settings
from telegram_outreach.infrastructure.persistence.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
db_url = settings.database_url

# Convert async driver URLs to their sync equivalents for Alembic
_sync_map = {
    "postgresql+asyncpg://": "postgresql+psycopg2://",
    "sqlite+aiosqlite:///": "sqlite:///",
    "sqlite+aiosqlite://": "sqlite:///",  # relative path fallback
    "mysql+aiomysql://": "mysql+pymysql://",
}
for k, v in _sync_map.items():
    if db_url.startswith(k):
        db_url = v + db_url[len(k):]
        break

config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
