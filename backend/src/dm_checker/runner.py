"""High level runner orchestrating worker pool."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from rich.console import Console
from rich.progress import Progress

from .config import AppSettings, load_settings
from .task_queue import TaskQueue
from .token_manager import TokenManager
from .proxy_manager import ProxyManager
from .worker import DMWorker

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.task_queue = TaskQueue(settings)
        self.token_manager = TokenManager(settings)
        self.proxy_manager = ProxyManager(settings)
        self._workers: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self.console = Console()

    async def start(self) -> None:
        await self.token_manager.load_tokens()
        await self.proxy_manager.load_proxies()
        if self.settings.resume_on_start:
            await self.task_queue.preload()
        worker_count = self.settings.concurrency.global_limit
        for worker_id in range(worker_count):
            worker = DMWorker(self.settings, self.task_queue, self.token_manager, self.proxy_manager)
            task = asyncio.create_task(worker.start(worker_id))
            self._workers.append(task)
        await self._stop_event.wait()

    async def stop(self) -> None:
        self._stop_event.set()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)


async def run(settings: Optional[AppSettings] = None) -> None:
    settings = settings or load_settings()
    runner = Runner(settings)
    await runner.start()


def create_runner(settings: Optional[AppSettings] = None) -> Runner:
    return Runner(settings or load_settings())
