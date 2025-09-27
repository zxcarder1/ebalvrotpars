"""Token pool with adaptive rate control."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import Deque, Optional

from sqlmodel import select

from .config import AppSettings
from .db import session_scope
from .models import Token, TokenState
from .rate_limiter import RateLimiter


class TokenManager:
    """Coordinates token reuse and cooldown logic."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._queue: Deque[int] = deque()
        self._limiter = RateLimiter()
        self._lock = asyncio.Lock()

    async def load_tokens(self) -> None:
        async with session_scope(self.settings) as session:
            result = await session.exec(select(Token))
            tokens = result.all()
        async with self._lock:
            self._queue.clear()
            for token in tokens:
                if token.state != TokenState.invalid:
                    self._queue.append(token.id)
                    self._limiter.configure(
                        token_id=token.id,
                        rps=max(self.settings.rate_plan.initial_rps, token.estimated_rps),
                        burst_capacity=self.settings.rate_plan.burst_capacity,
                    )

    async def acquire(self) -> Optional[int]:
        async with self._lock:
            if not self._queue:
                return None
            token_id = self._queue.popleft()
            self._queue.append(token_id)
        await self._limiter.wait_for_turn(token_id)
        return token_id

    async def update_on_success(self, token_id: int, new_rps: float | None = None) -> None:
        if new_rps is not None:
            self._limiter.update_rate(token_id, new_rps, self.settings.rate_plan.burst_capacity)
        async with session_scope(self.settings) as session:
            token = await session.get(Token, token_id)
            if token:
                token.state = TokenState.active
                token.consecutive_429 = 0
                token.last_response = "success"
                if new_rps is not None:
                    token.estimated_rps = new_rps

    async def update_on_rate_limit(self, token_id: int) -> None:
        cooldown = self.settings.rate_plan.cooldown_seconds
        new_rps: float | None = None
        async with session_scope(self.settings) as session:
            token = await session.get(Token, token_id)
            if token:
                token.state = TokenState.throttled
                token.last_429_at = datetime.utcnow()
                token.consecutive_429 += 1
                token.last_response = "rate_limited"
                new_rps = max(
                    self.settings.rate_plan.min_rps,
                    token.estimated_rps / (2 ** token.consecutive_429),
                )
                token.estimated_rps = new_rps
        if new_rps is not None:
            self._limiter.update_rate(token_id, new_rps, self.settings.rate_plan.burst_capacity)
        asyncio.create_task(self._reenqueue_after(token_id, cooldown))

    async def update_on_invalid(self, token_id: int, reason: str) -> None:
        async with session_scope(self.settings) as session:
            token = await session.get(Token, token_id)
            if token:
                token.state = TokenState.invalid
                token.last_response = reason
        async with self._lock:
            self._queue = deque([tid for tid in self._queue if tid != token_id])

    async def _reenqueue_after(self, token_id: int, delay: float) -> None:
        await asyncio.sleep(delay)
        async with session_scope(self.settings) as session:
            token = await session.get(Token, token_id)
            if not token or token.state == TokenState.invalid:
                return
            token.state = TokenState.cooling_down
            await session.commit()
        async with self._lock:
            if token_id not in self._queue:
                self._queue.append(token_id)
