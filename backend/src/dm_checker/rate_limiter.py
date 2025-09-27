"""Token-aware rate limiting utilities."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class TokenBudget:
    """Simple token bucket implementation for one credential."""

    token_id: int
    capacity: int
    refill_rate: float
    allowance: float
    last_check: float

    @classmethod
    def from_rps(cls, token_id: int, rps: float, burst_capacity: int) -> "TokenBudget":
        now = time.perf_counter()
        capacity = max(1, burst_capacity)
        return cls(
            token_id=token_id,
            capacity=capacity,
            refill_rate=rps,
            allowance=float(capacity),
            last_check=now,
        )

    def consume(self, amount: float = 1.0) -> float:
        """Consume allowance and return sleep duration if needed."""

        current = time.perf_counter()
        time_passed = current - self.last_check
        self.last_check = current
        self.allowance += time_passed * self.refill_rate
        if self.allowance > self.capacity:
            self.allowance = float(self.capacity)
        if self.allowance >= amount:
            self.allowance -= amount
            return 0.0
        needed = amount - self.allowance
        wait_time = needed / max(self.refill_rate, 1e-6)
        self.allowance = 0.0
        return max(0.0, wait_time)


class RateLimiter:
    """Async rate limiter built on token buckets."""

    def __init__(self):
        self._budgets: dict[int, TokenBudget] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def configure(self, token_id: int, rps: float, burst_capacity: int) -> None:
        budget = TokenBudget.from_rps(token_id, rps, burst_capacity)
        self._budgets[token_id] = budget
        self._locks.setdefault(token_id, asyncio.Lock())

    async def wait_for_turn(self, token_id: int, amount: float = 1.0) -> None:
        if token_id not in self._budgets:
            raise KeyError(f"Token {token_id} not registered")
        lock = self._locks[token_id]
        async with lock:
            budget = self._budgets[token_id]
            delay = budget.consume(amount)
            if delay > 0:
                await asyncio.sleep(delay)

    def update_rate(self, token_id: int, rps: float, burst_capacity: int) -> None:
        if token_id in self._budgets:
            self._budgets[token_id] = TokenBudget.from_rps(token_id, rps, burst_capacity)

    def reset(self, token_id: int) -> None:
        if token_id in self._budgets:
            budget = self._budgets[token_id]
            self._budgets[token_id] = TokenBudget.from_rps(
                token_id, budget.refill_rate, budget.capacity
            )
