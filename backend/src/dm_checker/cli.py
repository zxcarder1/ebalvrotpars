"""Command line entry points for DM checker backend."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .config import AppSettings, load_settings
from .parsers import parse_accounts, parse_proxies, parse_tokens
from .task_queue import TaskQueue
from .runner import run
from . import db
from . import models
from sqlmodel import SQLModel

app = typer.Typer(help="DM checker backend utilities")
console = Console()


@app.command()
def init_db(db_path: Optional[str] = None) -> None:
    """Initialise database schema."""

    settings = load_settings()
    if db_path:
        settings.database.dsn = db_path

    engine = db.get_engine(settings)
    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    asyncio.run(_create())
    console.print("Database initialised", style="green")


@app.command()
def ingest_accounts(path: Path) -> None:
    settings = load_settings()
    queue = TaskQueue(settings)
    accounts = parse_accounts(path)
    asyncio.run(queue.add_accounts(accounts))
    console.print(f"Loaded {len(accounts)} accounts", style="green")


@app.command()
def ingest_tokens(path: Path) -> None:
    settings = load_settings()
    records = parse_tokens(path)
    async def _ingest() -> None:
        async with db.session_scope(settings) as session:
            for record in records:
                token = models.Token(
                    login=record.login,
                    auth_token=record.auth_token,
                    ct0=record.ct0,
                    web_bearer=record.web_bearer,
                )
                session.add(token)
    asyncio.run(_ingest())
    console.print(f"Loaded {len(records)} tokens", style="green")


@app.command()
def ingest_proxies(path: Path) -> None:
    settings = load_settings()
    records = parse_proxies(path)
    async def _ingest() -> None:
        async with db.session_scope(settings) as session:
            for record in records:
                proxy = models.Proxy(raw=record.raw)
                session.add(proxy)
    asyncio.run(_ingest())
    console.print(f"Loaded {len(records)} proxies", style="green")


@app.command()
def serve() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    app()
