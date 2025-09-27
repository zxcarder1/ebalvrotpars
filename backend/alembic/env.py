from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

from dm_checker.config import load_settings
from dm_checker.db import get_engine
from dm_checker import models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = load_settings()


def run_migrations_offline() -> None:
    url = settings.database.dsn
    context.configure(
        url=url,
        target_metadata=SQLModel.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=SQLModel.metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = get_engine(settings)

    async def _run_migrations() -> None:
        async with connectable.connect() as connection:  # type: ignore[arg-type]
            await connection.run_sync(do_run_migrations)

    asyncio.run(_run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
