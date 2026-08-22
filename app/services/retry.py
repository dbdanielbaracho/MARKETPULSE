from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0

    def __post_init__(self) -> None:
        if self.attempts < 1 or self.attempts > 8:
            raise ValueError("attempts must be between 1 and 8")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("invalid retry delays")


async def with_retry(operation: Callable[[], Awaitable[T]], policy: RetryPolicy = RetryPolicy()) -> T:
    last_error: Exception | None = None
    for attempt in range(policy.attempts):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt == policy.attempts - 1:
                break
            cap = min(policy.base_delay_seconds * (2**attempt), policy.max_delay_seconds)
            await asyncio.sleep(random.uniform(0, cap))
    assert last_error is not None
    raise last_error
