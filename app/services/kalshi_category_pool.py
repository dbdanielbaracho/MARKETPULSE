from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from typing import Any

import httpx

from app.adapters.kalshi import KalshiAdapter
from app.domain.markets import NormalizedMarket

logger = logging.getLogger("marketpulse.kalshi.category_pool")

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
CATEGORY_POOL_TTL_SECONDS = 15 * 60
MAX_EVENT_PAGES_PER_SERIES = 3
_RATE_LIMIT_DELAYS = (0.5, 1.0, 2.0, 4.0)

# One Uvicorn worker is used in production. A small in-process cache prevents
# the category complement from multiplying Kalshi requests on each 5-minute
# refresh. The last good value is retained as a transient-failure fallback.
_CACHE: dict[tuple[str, tuple[str, ...]], tuple[float, list[NormalizedMarket]]] = {}


def _number(value: object) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def _series_rank(item: dict[str, Any]) -> float:
    return _number(item.get("volume_fp") or item.get("volume"))


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Fetch JSON with bounded 429 retry/backoff and no retry on hard 4xx."""
    for attempt in range(len(_RATE_LIMIT_DELAYS) + 1):
        response = await client.get(url, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        if attempt >= len(_RATE_LIMIT_DELAYS):
            response.raise_for_status()
        retry_after = response.headers.get("retry-after")
        try:
            wait = max(float(retry_after), 0.0) if retry_after is not None else _RATE_LIMIT_DELAYS[attempt]
        except (TypeError, ValueError):
            wait = _RATE_LIMIT_DELAYS[attempt]
        await asyncio.sleep(min(wait, 8.0))
    return {}


async def fetch_kalshi_category_pool(
    *,
    base_url: str,
    timeout_seconds: float = 10.0,
    categories: tuple[str, ...] = TARGET_SERIES_CATEGORIES,
    now_monotonic: float | None = None,
) -> list[NormalizedMarket]:
    """Return a bounded category-aware complement to Kalshi's global market scan.

    Kalshi category belongs to Series. The global /markets cursor is not
    category-aware and live production evidence showed its first 5,000 open
    contracts contained 0/1,029 Science & Technology markets and only 16/2,415
    Politics markets. This routine discovers high-signal Series and resolves
    their open Events with nested Markets before the existing ranking/quality
    gates run.

    Results are cached for 15 minutes. Event pagination is bounded to protect
    the provider but follows cursors so a busy Series is not silently truncated
    at its first 200 events. If any selected-Series fetch fails, a prior good
    cache is preferred and the partial result is not cached as authoritative.
    """
    root = base_url.rstrip("/")
    key = (root, tuple(categories))
    now = time.monotonic() if now_monotonic is None else now_monotonic
    cached = _CACHE.get(key)
    if cached is not None and now - cached[0] < CATEGORY_POOL_TTL_SECONDS:
        return list(cached[1])

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            payload = await _get_json(
                client,
                f"{root}/series",
                params={"include_volume": "true"},
            )
            rows = payload.get("series", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                rows = []

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

            semaphore = asyncio.Semaphore(3)

            async def fetch_series_events(
                category: str,
                series_ticker: str,
            ) -> tuple[list[dict[str, Any]], bool]:
                markets: list[dict[str, Any]] = []
                cursor: str | None = None
                try:
                    for _page_number in range(MAX_EVENT_PAGES_PER_SERIES):
                        params: dict[str, Any] = {
                            "series_ticker": series_ticker,
                            "status": "open",
                            "with_nested_markets": "true",
                            "limit": 200,
                        }
                        if cursor:
                            params["cursor"] = cursor
                        async with semaphore:
                            data = await _get_json(client, f"{root}/events", params=params)
                        events = data.get("events", []) if isinstance(data, dict) else []
                        if not isinstance(events, list):
                            events = []
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
                                if category and not item.get("category"):
                                    item["category"] = category
                                markets.append(item)
                        next_cursor = str(data.get("cursor") or "").strip() or None
                        if not next_cursor or next_cursor == cursor:
                            break
                        cursor = next_cursor
                    return markets, True
                except (httpx.HTTPError, ValueError, TypeError):
                    return markets, False

            resolved = await asyncio.gather(
                *(fetch_series_events(category, ticker) for category, ticker in selected_series)
            )

        groups = [markets for markets, _success in resolved]
        had_partial_failure = any(not success for _markets, success in resolved)
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

        selected_raw.sort(key=KalshiAdapter._activity_rank_key, reverse=True)
        selected_raw = selected_raw[:MAX_CATEGORY_MARKETS]
        normalized = [KalshiAdapter.normalize(item) for item in selected_raw]

        if had_partial_failure and cached is not None:
            logger.warning("kalshi category refresh partial; retaining last complete pool")
            return list(cached[1])
        if not had_partial_failure:
            _CACHE[key] = (now, list(normalized))
        logger.info(
            "kalshi category pool markets=%d coverage=%s partial=%s",
            len(normalized),
            ",".join(f"{category}:{coverage[category]}" for category in categories),
            had_partial_failure,
        )
        return normalized
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("kalshi category pool refresh unavailable: %s", type(exc).__name__)
        stale = _CACHE.get(key)
        return list(stale[1]) if stale is not None else []
