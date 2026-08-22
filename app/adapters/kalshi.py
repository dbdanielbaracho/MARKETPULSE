from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.domain.markets import NormalizedMarket


class KalshiAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch_markets(self, limit: int = 100, cursor: str | None = None) -> tuple[list[NormalizedMarket], str | None]:
        params: dict[str, Any] = {"limit": limit, "status": "open"}
        if cursor:
            params["cursor"] = cursor
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
        payload = response.json()
        return [self.normalize(item) for item in payload.get("markets", [])], payload.get("cursor")

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
        return NormalizedMarket(
            venue="kalshi",
            venue_market_id=ticker,
            title=str(item.get("title") or item.get("subtitle") or ticker),
            category=item.get("category"),
            yes_probability=probability,
            volume_usd=(
                float(item["volume_fp"])
                if item.get("volume_fp") is not None
                else float(item["volume"])
                if isinstance(item.get("volume"), (int, float))
                else None
            ),
            closes_at=closes_at,
            source_url=f"https://kalshi.com/markets/{ticker}" if ticker else None,
            raw=item,
        )
