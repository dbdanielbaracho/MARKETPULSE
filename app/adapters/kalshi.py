from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from app.domain.markets import NormalizedMarket
from app.services.categories import classify_market_category


class KalshiAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch_markets(self, limit: int = 100, cursor: str | None = None) -> tuple[list[NormalizedMarket], str | None]:
        params: dict[str, Any] = {"limit": limit, "status": "open", "mve_filter": "exclude"}
        if cursor:
            params["cursor"] = cursor
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
            payload = response.json()
            raw_markets = payload.get("markets", [])
            if not isinstance(raw_markets, list):
                raw_markets = []
            await self._enrich_missing_series_tickers(client, raw_markets)
            await self._enrich_series_metadata(client, raw_markets)
        return [self.normalize(item) for item in raw_markets], payload.get("cursor")

    async def _enrich_missing_series_tickers(
        self,
        client: httpx.AsyncClient,
        markets: list[dict[str, Any]],
    ) -> None:
        """Resolve missing series metadata from Kalshi's canonical Event endpoint."""
        missing_by_event: dict[str, list[dict[str, Any]]] = {}
        for item in markets:
            if not isinstance(item, dict) or str(item.get("series_ticker") or "").strip():
                continue
            event_ticker = str(item.get("event_ticker") or "").strip()
            if event_ticker:
                missing_by_event.setdefault(event_ticker, []).append(item)
        if not missing_by_event:
            return

        semaphore = asyncio.Semaphore(8)

        async def resolve(event_ticker: str) -> tuple[str, str | None]:
            try:
                async with semaphore:
                    response = await client.get(
                        f"{self.base_url}/events/{event_ticker}",
                        params={"with_nested_markets": "false"},
                    )
                    response.raise_for_status()
                payload = response.json()
                event = payload.get("event", {}) if isinstance(payload, dict) else {}
                series_ticker = str(event.get("series_ticker") or "").strip() if isinstance(event, dict) else ""
                return event_ticker, series_ticker or None
            except (httpx.HTTPError, ValueError, TypeError):
                return event_ticker, None

        results = await asyncio.gather(*(resolve(event_ticker) for event_ticker in missing_by_event))
        for event_ticker, series_ticker in results:
            if not series_ticker:
                continue
            for item in missing_by_event[event_ticker]:
                item["series_ticker"] = series_ticker

    async def _enrich_series_metadata(
        self,
        client: httpx.AsyncClient,
        markets: list[dict[str, Any]],
    ) -> None:
        """Attach Kalshi's canonical series category/tags to market rows.

        The markets endpoint does not reliably include a public category on every
        contract. Public PrediBeacon filters therefore resolve the parent series
        instead of guessing categories from arbitrary ticker strings.
        """
        by_series: dict[str, list[dict[str, Any]]] = {}
        for item in markets:
            if not isinstance(item, dict):
                continue
            series_ticker = str(item.get("series_ticker") or "").strip()
            if series_ticker:
                by_series.setdefault(series_ticker, []).append(item)
        if not by_series:
            return

        semaphore = asyncio.Semaphore(8)

        async def resolve(series_ticker: str) -> tuple[str, str | None, list[str]]:
            try:
                async with semaphore:
                    response = await client.get(f"{self.base_url}/series/{series_ticker}")
                    response.raise_for_status()
                payload = response.json()
                series = payload.get("series", {}) if isinstance(payload, dict) else {}
                if not isinstance(series, dict):
                    return series_ticker, None, []
                category = str(series.get("category") or "").strip() or None
                raw_tags = series.get("tags")
                tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()] if isinstance(raw_tags, list) else []
                return series_ticker, category, tags
            except (httpx.HTTPError, ValueError, TypeError):
                return series_ticker, None, []

        results = await asyncio.gather(*(resolve(series_ticker) for series_ticker in by_series))
        for series_ticker, category, tags in results:
            for item in by_series[series_ticker]:
                if category:
                    item["_predibeacon_series_category"] = category
                if tags:
                    item["_predibeacon_series_tags"] = tags

    async def fetch_market(self, ticker: str) -> dict[str, Any]:
        if not ticker or len(ticker) > 200:
            raise ValueError("invalid Kalshi ticker")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/markets/{ticker}")
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def fetch_orderbook(self, ticker: str, depth: int = 20) -> dict[str, Any]:
        if not ticker or len(ticker) > 200:
            raise ValueError("invalid Kalshi ticker")
        if depth < 1 or depth > 100:
            raise ValueError("depth must be between 1 and 100")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/markets/{ticker}/orderbook",
                params={"depth": depth},
            )
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def normalize(item: dict[str, Any]) -> NormalizedMarket:
        probability = None
        yes_bid_dollars = item.get("yes_bid_dollars")
        yes_ask_dollars = item.get("yes_ask_dollars")
        if yes_bid_dollars is not None and yes_ask_dollars is not None:
            probability = (float(yes_bid_dollars) + float(yes_ask_dollars)) / 2.0
        else:
            yes_bid = item.get("yes_bid")
            yes_ask = item.get("yes_ask")
            if isinstance(yes_bid, (int, float)) and isinstance(yes_ask, (int, float)):
                probability = ((float(yes_bid) + float(yes_ask)) / 2.0) / 100.0
            elif item.get("last_price_dollars") is not None:
                probability = float(item["last_price_dollars"])
            elif isinstance(item.get("last_price"), (int, float)):
                probability = float(item["last_price"]) / 100.0

        close_time = item.get("close_time")
        closes_at = datetime.fromisoformat(close_time.replace("Z", "+00:00")) if close_time else None
        ticker = str(item.get("ticker") or item.get("id") or "")
        series_ticker = str(item.get("series_ticker") or "").strip()
        title = str(item.get("title") or item.get("subtitle") or ticker)
        provider_category = item.get("category") or item.get("_predibeacon_series_category")
        return NormalizedMarket(
            venue="kalshi",
            venue_market_id=ticker,
            title=title,
            category=classify_market_category(title=title, provider_category=provider_category, raw=item),
            yes_probability=probability,
            # Kalshi volume_fp is contract volume, not a USD monetary value. The
            # current shared field is retained internally for activity ranking;
            # the public card presentation labels Kalshi values as contracts.
            volume_usd=(
                float(item["volume_fp"])
                if item.get("volume_fp") is not None
                else float(item["volume"])
                if isinstance(item.get("volume"), (int, float))
                else None
            ),
            closes_at=closes_at,
            source_url=f"https://kalshi.com/markets/{series_ticker.lower()}" if series_ticker else None,
            raw=item,
        )