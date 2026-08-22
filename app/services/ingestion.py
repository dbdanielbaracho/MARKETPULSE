from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from app.config.runtime import RuntimeFlags
from app.domain.markets import NormalizedMarket
from app.services.intelligence import MarketSignal, signal, snapshot
from app.services.retry import RetryPolicy, with_retry
from app.storage.snapshots import SnapshotStore


class MarketFetcher(Protocol):
    async def fetch_markets(self, limit: int = 100) -> object: ...


@dataclass(frozen=True)
class RefreshBatch:
    markets: tuple[NormalizedMarket, ...]
    signals: tuple[MarketSignal, ...]
    errors: tuple[str, ...]


class IngestionWorker:
    """Bounded public-data refresh worker with venue isolation and snapshot persistence."""

    def __init__(
        self,
        *,
        store: SnapshotStore,
        flags: RuntimeFlags,
        kalshi: MarketFetcher | None = None,
        polymarket: MarketFetcher | None = None,
        limit_per_venue: int = 100,
        retry_policy: RetryPolicy = RetryPolicy(),
    ) -> None:
        if not 1 <= limit_per_venue <= 1000:
            raise ValueError("limit_per_venue must be between 1 and 1000")
        self.store = store
        self.flags = flags
        self.kalshi = kalshi
        self.polymarket = polymarket
        self.limit_per_venue = limit_per_venue
        self.retry_policy = retry_policy

    async def _fetch(self, venue: str, fetcher: MarketFetcher | None) -> list[NormalizedMarket]:
        if not self.flags.venue_enabled(venue) or fetcher is None:
            return []

        async def operation() -> object:
            return await fetcher.fetch_markets(limit=self.limit_per_venue)

        result = await with_retry(operation, self.retry_policy)
        if isinstance(result, tuple):
            result = result[0]
        if not isinstance(result, list):
            raise TypeError(f"{venue} adapter returned an invalid market collection")
        return result

    async def refresh_once(self) -> RefreshBatch:
        markets: list[NormalizedMarket] = []
        errors: list[str] = []
        for venue, fetcher in (("kalshi", self.kalshi), ("polymarket", self.polymarket)):
            try:
                markets.extend(await self._fetch(venue, fetcher))
            except Exception as exc:
                errors.append(f"{venue}:{type(exc).__name__}")

        signals: list[MarketSignal] = []
        for market in markets:
            current = snapshot(market)
            previous = self.store.previous(current.canonical_id, current.observed_at.isoformat())
            self.store.append(current)
            signals.append(signal(current, previous))
        return RefreshBatch(tuple(markets), tuple(signals), tuple(errors))

    async def run_forever(
        self,
        *,
        interval_seconds: float,
        publish: Callable[[RefreshBatch], Awaitable[None] | None],
        stop: asyncio.Event,
    ) -> None:
        if interval_seconds < 5:
            raise ValueError("refresh interval must be at least 5 seconds")
        while not stop.is_set():
            batch = await self.refresh_once()
            published = publish(batch)
            if published is not None:
                await published
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass
