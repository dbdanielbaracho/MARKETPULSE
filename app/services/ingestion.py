from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol, runtime_checkable

from app.config.runtime import RuntimeFlags
from app.domain.markets import NormalizedMarket
from app.services.intelligence import MarketSignal, signal, snapshot
from app.services.kalshi_category_pool import fetch_kalshi_category_pool
from app.services.retry import RetryPolicy, is_transient_http_error, with_retry
from app.storage.snapshots import SnapshotStore


logger = logging.getLogger("marketpulse.ingestion")


@runtime_checkable
class MarketFetcher(Protocol):
    async def fetch_markets(self, limit: int = 100) -> object: ...


@dataclass(frozen=True)
class RefreshBatch:
    markets: tuple[NormalizedMarket, ...]
    signals: tuple[MarketSignal, ...]
    errors: tuple[str, ...]


def _is_open_market(market: NormalizedMarket, *, now: datetime) -> bool:
    """Fail closed when a contract deadline is invalid or no longer in the future."""
    closes_at = market.closes_at
    if closes_at is None:
        return True
    if closes_at.tzinfo is None or closes_at.utcoffset() is None:
        logger.warning("market has timezone-naive closes_at and will not enter active discovery: %s", market.canonical_id)
        return False
    return closes_at > now


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

        result = await with_retry(operation, self.retry_policy, should_retry=is_transient_http_error)
        if isinstance(result, tuple):
            result = result[0]
        if not isinstance(result, list):
            raise TypeError(f"{venue} adapter returned an invalid market collection")

        # Kalshi categories live on Series, while the global /markets cursor is
        # not category-aware. Production evidence proved that the first 5,000
        # open markets can omit all Science & Technology and virtually all
        # Politics contracts. Add a bounded Series->Events->Markets complement
        # before intelligence ranking; do not reserve display slots or weaken
        # any semantic quality floor.
        if venue == "kalshi":
            base_url = str(getattr(fetcher, "base_url", "") or "").strip()
            timeout_seconds = float(getattr(fetcher, "timeout_seconds", 10.0) or 10.0)
            if base_url:
                extras = await fetch_kalshi_category_pool(
                    base_url=base_url,
                    timeout_seconds=timeout_seconds,
                )
                if extras:
                    merged: list[NormalizedMarket] = []
                    seen: set[str] = set()
                    for market in [*result, *extras]:
                        canonical_id = getattr(market, "canonical_id", "")
                        if not canonical_id or canonical_id in seen:
                            continue
                        seen.add(canonical_id)
                        merged.append(market)
                    result = merged
                    logger.info(
                        "kalshi candidate universe broadened global=%d category_aware=%d merged=%d",
                        len(result) - len(extras),
                        len(extras),
                        len(result),
                    )
        return result

    async def refresh_once(self) -> RefreshBatch:
        markets: list[NormalizedMarket] = []
        errors: list[str] = []
        for venue, fetcher in (("kalshi", self.kalshi), ("polymarket", self.polymarket)):
            try:
                markets.extend(await self._fetch(venue, fetcher))
            except Exception as exc:
                error = f"{venue}:{type(exc).__name__}"
                errors.append(error)
                logger.warning("venue refresh failed: %s", error)

        processed: list[NormalizedMarket] = []
        signals: list[MarketSignal] = []
        now = datetime.now(timezone.utc)
        for market in markets:
            if not _is_open_market(market, now=now):
                logger.info("excluding non-open market from active discovery: %s", market.canonical_id)
                continue
            try:
                current = snapshot(market)
                previous = self.store.previous(current.canonical_id, current.observed_at.isoformat())
                self.store.append(current)
                signals.append(signal(current, previous))
                processed.append(market)
            except Exception as exc:
                error = f"storage:{type(exc).__name__}"
                errors.append(error)
                logger.exception("market snapshot failed for %s", market.canonical_id)
        logger.info(
            "refresh complete markets=%d errors=%d venues_enabled=%s",
            len(processed),
            len(errors),
            ",".join(venue for venue in ("kalshi", "polymarket") if self.flags.venue_enabled(venue)),
        )
        return RefreshBatch(tuple(processed), tuple(signals), tuple(errors))

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
