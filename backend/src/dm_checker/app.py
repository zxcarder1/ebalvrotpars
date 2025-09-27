"""FastAPI app exposing control plane for the DM checker."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import AppSettings, load_settings
from .models import AccountStatus
from .parsers import parse_accounts, parse_proxies, parse_tokens
from .task_queue import TaskQueue
from .token_manager import TokenManager
from .proxy_manager import ProxyManager


class LoadRequest(BaseModel):
    accounts_file: Path | None = None
    tokens_file: Path | None = None
    proxies_file: Path | None = None


class ProgressResponse(BaseModel):
    checked: int
    pending: int
    skipped: int
    errors: int
    active_tokens: int
    active_proxies: int


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or load_settings()
    task_queue = TaskQueue(settings)
    token_manager = TokenManager(settings)
    proxy_manager = ProxyManager(settings)

    app = FastAPI(title="DM Checker Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ui_allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup() -> None:
        await token_manager.load_tokens()
        await proxy_manager.load_proxies()
        if settings.resume_on_start:
            await task_queue.preload()

    async def get_task_queue() -> TaskQueue:
        return task_queue

    @app.post("/load")
    async def load_files(payload: LoadRequest, queue: TaskQueue = Depends(get_task_queue)) -> dict:
        if payload.accounts_file:
            accounts = parse_accounts(payload.accounts_file)
            await queue.add_accounts(accounts)
        if payload.tokens_file:
            records = parse_tokens(payload.tokens_file)
            # tokens ingestion deferred to CLI tool for now
            pass
        if payload.proxies_file:
            parse_proxies(payload.proxies_file)
            # proxies ingestion deferred
        return {"status": "ok"}

    @app.get("/progress", response_model=ProgressResponse)
    async def progress(queue: TaskQueue = Depends(get_task_queue)) -> ProgressResponse:
        # placeholder stats using DB counts
        # In real version gather counts via queries
        return ProgressResponse(
            checked=0,
            pending=queue._queue.qsize(),
            skipped=0,
            errors=0,
            active_tokens=len(token_manager._queue),
            active_proxies=len(proxy_manager._queue),
        )

    return app

