"""Persistent task queue implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select

from .config import AppSettings
from .db import session_scope
from .models import Account, AccountStatus


@dataclass
class AccountTask:
    id: int
    screen_name: str


class TaskQueue:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._queue: asyncio.Queue[AccountTask] = asyncio.Queue()
        self._loader_lock = asyncio.Lock()

    async def preload(self) -> None:
        """Load pending accounts from the database into memory."""

        async with self._loader_lock:
            async with session_scope(self.settings) as session:
                ttl_cutoff = datetime.utcnow() - timedelta(hours=self.settings.account_ttl_hours)
                statement = select(Account).where(
                    (Account.status == AccountStatus.pending)
                    | (Account.last_checked_at == None)
                    | (Account.last_checked_at < ttl_cutoff)
                )
                result = await session.exec(statement)
                accounts = result.all()
            for account in accounts:
                await self._queue.put(AccountTask(id=account.id, screen_name=account.screen_name))

    async def add_accounts(self, accounts: list[str]) -> None:
        async with session_scope(self.settings) as session:
            for screen_name in accounts:
                existing = await session.exec(
                    select(Account).where(Account.screen_name == screen_name)
                )
                row = existing.one_or_none()
                if row and self.settings.skip_duplicates:
                    if row.last_checked_at:
                        ttl_cutoff = datetime.utcnow() - timedelta(hours=self.settings.account_ttl_hours)
                        if row.last_checked_at >= ttl_cutoff:
                            continue
                if row:
                    account = row
                    account.status = AccountStatus.pending
                else:
                    account = Account(screen_name=screen_name)
                session.add(account)
                await session.flush()
                await self._queue.put(AccountTask(id=account.id, screen_name=account.screen_name))

    async def get(self) -> AccountTask:
        task = await self._queue.get()
        async with session_scope(self.settings) as session:
            account = await session.get(Account, task.id)
            if account:
                account.status = AccountStatus.checking
                account.attempt_count += 1
        return task

    def task_done(self) -> None:
        self._queue.task_done()

    async def mark_result(
        self,
        task: AccountTask,
        status: AccountStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        async with session_scope(self.settings) as session:
            account = await session.get(Account, task.id)
            if account:
                account.status = status
                account.last_result = result
                account.error = error
                account.last_checked_at = datetime.utcnow()

