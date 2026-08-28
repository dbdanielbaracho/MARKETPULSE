from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

import httpx

from app.adapters.kalshi import KalshiAdapter
from app.domain.markets import NormalizedMarket

logger = logging.getLogger("marketpulse.kalshi.category_pool")

# Official Kalshi series categories that materially broaden PrediBeacon beyond
# the sports-heavy ordering of the global /markets cursor. This is discovery,
# not a display quota: candidates still compete under the existing ranking and
# semantic quality gates after ingestion.
TARGET_SERIES_CATEGORIES = (
    "Politics",
    "Science and Technology",
    "Economics",
    "Crypto",
    "Companies",
    "Elections",
)
SERIES_PER_CATEGORY = 5
MAX_MARKETS_PER_CATEGORY = 30
MAX_CATEGORY_MARKETS = 120


def _number(value: object) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def _series_rank(item: dict[str, Any]) -> float:
    # Series exposes aggregate provider volume. It is used only to choose a
    # bounded set of series to inspect; final market ranking still uses 24h
    # market activity via KalshiAdapter._activity_rank_key.
    return _number(item.get("volume_fp") or item.get("volume"))


async def fetch_kalshi_category_pool(
    *,
    base_url: str,
    timeout_seconds: float = 10.0,
    categories: tuple[str, ...] = TARGET_SERIES_CATEGORIES,
) -> list[NormalizedMarket]:
    """Return a bounded category-aware complement to Kalshi's global market scan.

    Kalshi's category is a Series property. The global /markets cursor is not
    category-aware and production evidence showed that its first 5,000 open
    contracts contained 0/1,029 Science & Technology markets and only 16/2,415
    Politics markets. This routine intentionally discovers Series first, then
    resolves open Events with nested Markets for a small high-signal subset.

    Failure is soft: the existing global Kalshi pool remains the fallback.
    """
    root = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{root}/series", params={"include_volume": "true"})
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("series", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                return []

            selected_series: list[tuple[str, str]] = []
            for category in categories:
                matches = [
                    item for item in rows
                    if isinstance(item, dict) and str(item.get("category") or "").strip() == category
                ]
                matches.sort(key=_series_rank, reverse=True)
                for item in matches[:SERIES_PER_CATEGORY]:
                    ticker = str(item.get("ticker") or "").strip()
                    if ticker:
                        selected_series.append((category, ticker))

            semaphore = asyncio.Semaphore(4)

            async def fetch_series_events(category: str, series_ticker: str) -> list[dict[str, Any]]:
                try:
                    async with semaphore:
                        result = await client.get(
                            f"{root}/events",
                            params={
                                "series_ticker": series_ticker,
                                "status": "open",
                                "with_nested_markets": "true",
                                "limit": 200,
                            },
                        )
                        result.raise_for_status()
                    data = result.json()
                except (httpx.HTTPError, ValueError, TypeError):
                    return []
                events = data.get("events", []) if isinstance(data, dict) else []
                if not isinstance(events, list):
                    return []
                markets: list[dict[str, Any]] = []
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    event_ticker = str(event.get("event_ticker") or event.get("ticker") or "").strip()
                    series = str(event.get("series_ticker") or series_ticker).strip()
                    nested = event.get("markets")
                    if not isinstance(nested, list):
                        continue
                    for raw in nested:
                        if not isinstance(raw, dict):
                            continue
                        item = dict(raw)
                        if event_ticker and not item.get("event_ticker"):
                            item["event_ticker"] = event_ticker
                        if series and not item.get("series_ticker"):
                            item["series_ticker"] = series
                        item["_predibeacon_series_category"] = category
                        markets.append(item)
                return markets

            groups = await asyncio.gather(
                *(fetch_series_events(category, ticker) for category, ticker in selected_series)
            )

        by_category: dict[str, list[dict[str, Any]]] = {category: [] for category in categories}
        seen: set[str] = set()
        for (category, _), markets in zip(selected_series, groups):
            for item in markets:
                ticker = str(item.get("ticker") or item.get("id") or "").strip()
                if not ticker or ticker in seen:
                    continue
                seen.add(ticker)
                by_category[category].append(item)

        selected_raw: list[dict[str, Any]] = []
        coverage = Counter()
        for category in categories:
            items = by_category.get(category, [])
            items.sort(key=KalshiAdapter._activity_rank_key, reverse=True)
            chosen = items[:MAX_MARKETS_PER_CATEGORY]
            selected_raw.extend(chosen)
            coverage[category] = len(chosen)

        # Final global cap is only a network/refresh bound, not a category quota.
        selected_raw.sort(key=KalshiAdapter._activity_rank_key, reverse=True)
        selected_raw = selected_raw[:MAX_CATEGORY_MARKETS]
        normalized = [KalshiAdapter.normalize(item) for item in selected_raw]
        logger.info(
            "kalshi category pool markets=%d coverage=%s",
            len(normalized),
            ",".join(f"{category}:{coverage[category]}" for category in categories),
        )
        return normalized
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("kalshi category pool unavailable: %s", type(exc).__name__)
        return []
