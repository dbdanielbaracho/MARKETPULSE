from __future__ import annotations

from typing import Any

import httpx


class KalshiTradesAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch_trades(self, *, ticker: str, limit: int = 200) -> list[dict[str, Any]]:
        if not ticker or len(ticker) > 200:
            raise ValueError("invalid Kalshi ticker")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/markets/trades",
                params={"ticker": ticker, "limit": limit},
            )
            response.raise_for_status()
        payload = response.json()
        return list(payload.get("trades") or []) if isinstance(payload, dict) else []


class PolymarketTradesAdapter:
    def __init__(
        self,
        base_url: str = "https://data-api.polymarket.com",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch_trades(self, *, condition_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if not condition_id or len(condition_id) > 300:
            raise ValueError("invalid Polymarket condition id")
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/trades",
                params={"market": condition_id, "limit": limit, "offset": 0},
            )
            response.raise_for_status()
        payload = response.json()
        return list(payload) if isinstance(payload, list) else list(payload.get("data") or []) if isinstance(payload, dict) else []
