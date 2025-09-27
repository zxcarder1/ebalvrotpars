"""Worker implementations for performing DM checks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
import aiofiles
from tenacity import AsyncRetrying, RetryError, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from .config import AppSettings
from .db import session_scope
from .models import AccountStatus, Check, Proxy, Token
from .proxy_manager import ProxyManager
from .task_queue import AccountTask, TaskQueue
from .token_manager import TokenManager

logger = logging.getLogger(__name__)


@dataclass
class DMResult:
    status: AccountStatus
    can_dm: Optional[bool]
    snippet: Optional[str]


class DMWorker:
    """Coordinates DM checks across tokens and proxies."""

    def __init__(
        self,
        settings: AppSettings,
        task_queue: TaskQueue,
        token_manager: TokenManager,
        proxy_manager: ProxyManager,
    ):
        self.settings = settings
        self.task_queue = task_queue
        self.token_manager = token_manager
        self.proxy_manager = proxy_manager
        self._client_pool: dict[int, httpx.AsyncClient] = {}
        self._client_lock = asyncio.Lock()
        self._token_cache: dict[int, Token] = {}

    async def start(self, worker_id: int) -> None:
        logger.info("Worker %s starting", worker_id)
        while True:
            task = await self.task_queue.get()
            try:
                await self._process_task(worker_id, task)
            except Exception:  # noqa: BLE001
                logger.exception("Worker %s crashed while processing %s", worker_id, task)
                await self.task_queue.mark_result(task, AccountStatus.error, error="internal_error")
            finally:
                self.task_queue.task_done()

    async def _process_task(self, worker_id: int, task: AccountTask) -> None:
        token_id = await self.token_manager.acquire()
        if not token_id:
            logger.warning("Worker %s cannot obtain token", worker_id)
            await asyncio.sleep(1.0)
            await self.task_queue.mark_result(task, AccountStatus.pending)
            return
        proxy_id = await self.proxy_manager.acquire()
        try:
            result = await self._execute_with_retry(token_id, proxy_id, task)
            await self._record_result(task, token_id, proxy_id, result)
        except RetryError as exc:
            logger.error("Task %s failed after retries: %s", task, exc)
            await self.task_queue.mark_result(task, AccountStatus.error, error="retry_exhausted")
            await self.token_manager.update_on_rate_limit(token_id)
            if proxy_id:
                await self.proxy_manager.release(proxy_id, failed=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error for %s: %s", task, exc)
            await self.task_queue.mark_result(task, AccountStatus.error, error=str(exc))
            await self.token_manager.update_on_rate_limit(token_id)
            if proxy_id:
                await self.proxy_manager.release(proxy_id, failed=True)
        else:
            await self.token_manager.update_on_success(token_id)
            if proxy_id:
                await self.proxy_manager.release(proxy_id, failed=False)

    async def _execute_with_retry(
        self,
        token_id: int,
        proxy_id: Optional[int],
        task: AccountTask,
    ) -> DMResult:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.settings.concurrency.retry_attempts),
            wait=wait_random_exponential(
                multiplier=self.settings.concurrency.retry_backoff_base,
                max=self.settings.concurrency.retry_backoff_max,
            ),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                client = await self._get_client(token_id, proxy_id)
                return await self._perform_check(client, task)
        raise RuntimeError("retry loop exited unexpectedly")

    async def _perform_check(self, client: httpx.AsyncClient, task: AccountTask) -> DMResult:
        """Call X endpoints to determine DM availability."""

        # Placeholder implementation; to be replaced with real logic.
        response = await client.get("https://example.com/health")
        if response.status_code == 200:
            snippet = response.text[:120]
            return DMResult(status=AccountStatus.checked, can_dm=True, snippet=snippet)
        if response.status_code == 403:
            return DMResult(status=AccountStatus.checked, can_dm=False, snippet="forbidden")
        if response.status_code == 429:
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
        raise httpx.HTTPStatusError("unexpected", request=response.request, response=response)

    async def _get_client(self, token_id: int, proxy_id: Optional[int]) -> httpx.AsyncClient:
        async with self._client_lock:
            if token_id in self._client_pool:
                return self._client_pool[token_id]
            token = await self._get_token(token_id)
            proxy = await self._get_proxy(proxy_id) if proxy_id else None
            client = self._build_client(token, proxy)
            self._client_pool[token_id] = client
            return client

    async def _get_token(self, token_id: int) -> Token:
        token = self._token_cache.get(token_id)
        if token:
            return token
        async with session_scope(self.settings) as session:
            token = await session.get(Token, token_id)
            if token is None:
                raise RuntimeError(f"Token {token_id} missing")
            self._token_cache[token_id] = token
            return token

    async def _get_proxy(self, proxy_id: int) -> Optional[Proxy]:
        async with session_scope(self.settings) as session:
            proxy = await session.get(Proxy, proxy_id)
            return proxy

    def _build_client(self, token: Token, proxy: Optional[Proxy]) -> httpx.AsyncClient:
        cookies = {
            "auth_token": token.auth_token,
            "ct0": token.ct0,
        }
        headers = {
            "authorization": token.web_bearer,
            "x-csrf-token": token.ct0,
            "user-agent": "DMChecker/0.1",
        }
        proxy_url = proxy.raw if proxy else None
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                self.settings.concurrency.request_timeout,
                connect=self.settings.concurrency.connect_timeout,
            ),
            headers=headers,
            cookies=cookies,
            proxy=proxy_url,
        )
        return client

    async def _record_result(
        self,
        task: AccountTask,
        token_id: int,
        proxy_id: Optional[int],
        result: DMResult,
    ) -> None:
        await self.task_queue.mark_result(task, result.status, result=result.snippet)
        if result.can_dm:
            path = self.settings.export_dir / "open_dm_accounts.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, "a", encoding="utf-8") as fp:
                await fp.write(f"{task.screen_name}\n")
        async with session_scope(self.settings) as session:
            check = Check(
                account_id=task.id,
                token_id=token_id,
                proxy_id=proxy_id,
                response_code=200 if result.can_dm else (403 if result.can_dm is False else None),
                response_body_snippet=result.snippet,
            )
            session.add(check)

