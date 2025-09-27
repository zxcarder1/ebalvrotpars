"""Proxy rotation and accounting."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import Deque, Optional

from sqlmodel import select

from .config import AppSettings
from .db import session_scope
from .models import Proxy


class ProxyManager:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._queue: Deque[int] = deque()
        self._inflight: dict[int, int] = {}
        self._lock = asyncio.Lock()

    async def load_proxies(self) -> None:
        async with session_scope(self.settings) as session:
            result = await session.exec(select(Proxy))
            proxies = result.all()
        async with self._lock:
            self._queue.clear()
            self._inflight.clear()
            for proxy in proxies:
                self._queue.append(proxy.id)

    async def acquire(self) -> Optional[int]:
        async with self._lock:
            if not self._queue:
                return None
            proxy_id = self._queue.popleft()
            count = self._inflight.get(proxy_id, 0)
            if count >= self.settings.concurrency.per_proxy_limit:
                self._queue.append(proxy_id)
                return None
            self._inflight[proxy_id] = count + 1
            self._queue.append(proxy_id)
            return proxy_id

    async def release(self, proxy_id: int, failed: bool = False) -> None:
        async with self._lock:
            if proxy_id in self._inflight:
                self._inflight[proxy_id] = max(0, self._inflight[proxy_id] - 1)
        async with session_scope(self.settings) as session:
            proxy = await session.get(Proxy, proxy_id)
            if proxy:
                proxy.last_used_at = datetime.utcnow()
                if failed:
                    proxy.fails += 1
                else:
                    proxy.fails = max(0, proxy.fails - 1)

