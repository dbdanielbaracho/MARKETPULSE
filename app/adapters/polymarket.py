from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from app.domain.markets import NormalizedMarket
from app.services.categories import classify_market_category


class PolymarketAdapter:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        clob_base_url: str = "https://clob.polymarket.com",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.clob_base_url = clob_base_url.rstrip("/")

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

    async def fetch_market(self, market_id: str) -> dict[str, Any]:
        """Fetch a single Gamma market so CLOB/trade identifiers can be resolved."""
        if not market_id or len(market_id) > 300:
            raise ValueError("invalid Polymarket market id")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/markets/{market_id}")
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def fetch_orderbook(self, token_id: str) -> dict[str, Any]:
        """Fetch the public CLOB order book for one outcome token."""
        if not token_id or len(token_id) > 300:
            raise ValueError("invalid Polymarket token id")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.clob_base_url}/book",
                params={"token_id": token_id},
            )
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def yes_token_id(item: dict[str, Any]) -> str | None:
        """Return the YES token id from a Gamma market when exposed."""
        tokens = item.get("clobTokenIds") or item.get("clob_token_ids")
        if isinstance(tokens, str):
            try:
                tokens = json.loads(tokens)
            except json.JSONDecodeError:
                return None
        outcomes = item.get("outcomes")
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except json.JSONDecodeError:
                outcomes = None
        if isinstance(tokens, list) and tokens:
            if isinstance(outcomes, list) and len(outcomes) == len(tokens):
                for index, outcome in enumerate(outcomes):
                    if str(outcome).strip().casefold() == "yes":
                        return str(tokens[index])
            return str(tokens[0])
        return None

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = float(value)
        elif isinstance(value, str):
            try:
                number = float(value)
            except ValueError:
                return None
        else:
            return None
        return number if number >= 0 else None

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
        event_slug = None
        events = item.get("events")
        if isinstance(events, list):
            event_slug = next(
                (
                    event.get("slug")
                    for event in events
                    if isinstance(event, dict) and event.get("slug")
                ),
                None,
            )
        destination_slug = event_slug or slug
        title = str(item.get("question") or item.get("title") or market_id)
        return NormalizedMarket(
            venue="polymarket",
            venue_market_id=market_id,
            title=title,
            category=classify_market_category(title=title, provider_category=item.get("category"), raw=item),
            yes_probability=probability,
            # Gamma exposes numeric lifetime and trailing-24h volume separately.
            volume_usd=PolymarketAdapter._number(item.get("volumeNum")),
            volume_24h_usd=PolymarketAdapter._number(item.get("volume24hr")),
            closes_at=closes_at,
            source_url=f"https://polymarket.com/event/{destination_slug}" if destination_slug else None,
            raw=item,
        )
