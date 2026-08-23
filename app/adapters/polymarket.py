from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from app.domain.markets import NormalizedMarket
from app.services.categories import classify_market_category


class PolymarketAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch_markets(self, limit: int = 100, after: str | None = None) -> list[NormalizedMarket]:
        params: dict[str, Any] = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        }
        if after:
            params["after"] = after
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
        payload = response.json()
        items = payload if isinstance(payload, list) else payload.get("data", [])
        return [self.normalize(item) for item in items]

    @staticmethod
    def normalize(item: dict[str, Any]) -> NormalizedMarket:
        probability = None
        prices = item.get("outcomePrices")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except json.JSONDecodeError:
                prices = None
        if isinstance(prices, list) and prices:
            try:
                probability = float(prices[0])
            except (TypeError, ValueError):
                probability = None

        end_date = item.get("endDate") or item.get("end_date_iso")
        closes_at = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if isinstance(end_date, str) and end_date else None
        market_id = str(item.get("id") or item.get("conditionId") or item.get("slug") or "")
        slug = item.get("slug")
        title = str(item.get("question") or item.get("title") or market_id)
        return NormalizedMarket(
            venue="polymarket",
            venue_market_id=market_id,
            title=title,
            category=classify_market_category(title=title, provider_category=item.get("category"), raw=item),
            yes_probability=probability,
            volume_usd=float(item["volumeNum"]) if isinstance(item.get("volumeNum"), (int, float)) else None,
            closes_at=closes_at,
            source_url=f"https://polymarket.com/event/{slug}" if slug else None,
            raw=item,
        )
