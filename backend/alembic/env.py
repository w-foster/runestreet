from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.settings import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (import ensures models are registered)


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def _database_url() -> str:
    # Prefer env var so alembic works in Railway and locally.
    url = os.getenv("DATABASE_URL")
    if url:
        if "://" in url:
            scheme, rest = url.split("://", 1)
            if "+" not in scheme and scheme in ("postgres", "postgresql"):
                return f"postgresql+psycopg://{rest}"
        return url
    return settings.sqlalchemy_database_url()


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
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


