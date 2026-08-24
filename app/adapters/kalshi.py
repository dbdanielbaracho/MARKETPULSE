from __future__ import annotations

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
        return [self.normalize(item) for item in payload.get("markets", [])], payload.get("cursor")

    async def fetch_market(self, ticker: str) -> dict[str, Any]:
        """Fetch full public contract metadata, including venue resolution rules."""
        if not ticker or len(ticker) > 200:
            raise ValueError("invalid Kalshi ticker")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/markets/{ticker}")
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def fetch_orderbook(self, ticker: str, depth: int = 20) -> dict[str, Any]:
        """Fetch public displayed order-book levels for one Kalshi market.

        This endpoint is read-only. PrediBeacon uses it only to describe visible
        spread/depth; it does not place orders or infer guaranteed execution.
        """
        if not ticker or len(ticker) > 200:
            raise ValueError("invalid Kalshi ticker")
        if depth < 1 or depth > 100:
            raise ValueError("invalid Kalshi ticker")
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
        return NormalizedMarket(
            venue="kalshi",
            venue_market_id=ticker,
            title=title,
            category=classify_market_category(title=title, provider_category=item.get("category"), raw=item),
            yes_probability=probability,
            volume_usd=(
                float(item["volume_fp"])
                if item.get("volume_fp") is not None
                else float(item["volume"])
                if isinstance(item.get("volume"), (int, float))
                else None
            ),
            closes_at=closes_at,
            # Kalshi's public documentation links the web UI by series ticker,
            # while the Trade API uses the individual market ticker for contract
            # endpoints. Never guess a UI slug from a contract ticker.
            source_url=f"https://kalshi.com/markets/{series_ticker.lower()}" if series_ticker else None,
            raw=item,
        )
