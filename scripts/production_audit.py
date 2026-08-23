from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from collections import Counter
from urllib.parse import urlparse

import httpx


ESSENTIAL_PAGES = (
    "/", "/top", "/watchlist", "/alerts", "/methodology", "/risk",
    "/privacy", "/terms", "/articles", "/manifest.webmanifest",
)
PUBLIC_CATEGORIES = ("Economy", "Politics", "Sports", "Tech")


class Audit:
    def __init__(self, base_url: str, market_limit: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.market_limit = market_limit
        self.failures: list[str] = []
        self.checks = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(message)

    async def get(self, client: httpx.AsyncClient, path: str, **kwargs) -> httpx.Response | None:
        try:
            response = await client.get(f"{self.base_url}{path}", **kwargs)
        except Exception as exc:
            self.failures.append(f"GET {path} raised {type(exc).__name__}: {exc}")
            return None
        self.require(response.status_code == 200, f"GET {path} returned {response.status_code}")
        return response

    async def wait_for_version(
        self, client: httpx.AsyncClient, expected_version: str | None, timeout_seconds: int
    ) -> dict:
        deadline = time.monotonic() + timeout_seconds
        while True:
            response = await self.get(client, "/health")
            if response is not None and response.status_code == 200:
                payload = response.json()
                if not expected_version or payload.get("version") == expected_version:
                    return payload
            if time.monotonic() >= deadline:
                actual = response.json().get("version") if response is not None else None
                self.failures.append(
                    f"deployment version did not become {expected_version!r}; actual={actual!r}"
                )
                return {}
            await asyncio.sleep(10)

    async def audit_page(self, client: httpx.AsyncClient, path: str) -> None:
        response = await self.get(client, path)
        if response is None or response.status_code != 200:
            return
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            body = response.text
            self.require("<html" in body.casefold(), f"{path} is not an HTML document")
            self.require("MarketPulse" not in body, f"{path} exposes internal MarketPulse brand")
            self.require(
                body.casefold().count("<script") == body.casefold().count("</script>"),
                f"{path} has unbalanced script tags",
            )
    async def audit_polymarket_destination(
        self, client: httpx.AsyncClient, market: dict
    ) -> None:
        source_url = market.get("source_url")
        self.require(bool(source_url), f"{market.get('canonical_id')} has no source_url")
        if not source_url:
            return
        parsed = urlparse(source_url)
        parts = [part for part in parsed.path.split("/") if part]
        self.require(
            parsed.netloc == "polymarket.com" and len(parts) == 2 and parts[0] == "event",
            f"{market.get('canonical_id')} has malformed Polymarket URL: {source_url}",
        )
        if len(parts) != 2:
            return
        response = await client.get(
            "https://gamma-api.polymarket.com/events",
            params={"slug": parts[1], "limit": 1},
        )
        self.require(
            response.status_code == 200,
            f"Polymarket event validation returned {response.status_code}: {source_url}",
        )
        if response.status_code == 200:
            payload = response.json()
            self.require(
                isinstance(payload, list) and bool(payload),
                f"Polymarket event does not exist: {source_url}",
            )

    async def audit_kalshi_destination(
        self, client: httpx.AsyncClient, market: dict
    ) -> None:
        ticker = str(market.get("canonical_id", "")).partition(":")[2]
        self.require(bool(ticker), f"Kalshi market lacks ticker: {market.get('canonical_id')}")
        if not ticker:
            return
        response = await client.get(
            f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
        )
        self.require(
            response.status_code == 200,
            f"Kalshi market does not resolve through provider API: {ticker} ({response.status_code})",
        )

    async def audit_market(self, client: httpx.AsyncClient, market: dict) -> None:
        canonical_id = market["canonical_id"]
        slug = market.get("slug")
        self.require(bool(slug), f"{canonical_id} has no canonical slug")
        if slug:
            page = await self.get(client, f"/markets/{slug}")
            if page is not None and page.status_code == 200:
                self.require(
                    canonical_id in page.text,
                    f"/markets/{slug} does not embed its canonical market id",
                )

        detail = await self.get(
            client, "/api/v1/market", params={"market_id": canonical_id}
        )
        if detail is not None and detail.status_code == 200:
            self.require(
                detail.json().get("canonical_id") == canonical_id,
                f"market detail identity mismatch for {canonical_id}",
            )

        route = await self.get(
            client, "/api/v1/market/route", params={"market_id": canonical_id}
        )
        if route is not None and route.status_code == 200:
            route_payload = route.json()
            self.require(
                route_payload.get("available") is True,
                f"outbound route unavailable for {canonical_id}",
            )

        for hours in (24, 168, 720):
            history = await self.get(
                client,
                "/api/v1/market/history",
                params={"market_id": canonical_id, "hours": hours},
            )
            if history is not None and history.status_code == 200:
                self.require(isinstance(history.json(), list), f"invalid history for {canonical_id}")

        if market.get("venue") == "polymarket":
            await self.audit_polymarket_destination(client, market)
        elif market.get("venue") == "kalshi":
            await self.audit_kalshi_destination(client, market)

    async def run(self, expected_version: str | None, deploy_timeout: int) -> int:
        timeout = httpx.Timeout(20.0)
        limits = httpx.Limits(max_connections=12, max_keepalive_connections=6)
        async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=False) as client:
            health = await self.wait_for_version(client, expected_version, deploy_timeout)
            self.require(health.get("status") == "ok", "health status is not ok")

            status = await self.get(client, "/api/v1/status")
            if status is not None and status.status_code == 200:
                payload = status.json()
                self.require(payload.get("freshness") == "fresh", "production data is not fresh")
                self.require(payload.get("storage", {}).get("writable") is True, "storage is not writable")
                self.require(
                    payload.get("database_backup", {}).get("last_integrity") == "ok",
                    "latest database backup is not integral",
                )

            await asyncio.gather(*(self.audit_page(client, path) for path in ESSENTIAL_PAGES))

            response = await self.get(
                client, "/api/v1/markets", params={"limit": self.market_limit}
            )
            markets = response.json() if response is not None and response.status_code == 200 else []
            self.require(bool(markets), "discovery API returned no markets")
            counts = Counter(item.get("category") for item in markets)
            for category in PUBLIC_CATEGORIES:
                filtered = await self.get(
                    client,
                    "/api/v1/markets",
                    params={"limit": self.market_limit, "category": category},
                )
                items = filtered.json() if filtered is not None and filtered.status_code == 200 else []
                self.require(bool(items), f"{category} filter returned no markets")
                self.require(
                    all(item.get("category") == category for item in items),
                    f"{category} filter returned another category",
                )

            await asyncio.gather(*(self.audit_market(client, market) for market in markets))

        print(f"production audit: {self.checks} checks, {len(self.failures)} failures")
        if self.failures:
            for failure in self.failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            return 1
        print("PASS: PrediBeacon production journeys and provider destinations are healthy")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PrediBeacon production end to end")
    parser.add_argument("--base-url", default="https://predibeacon.com")
    parser.add_argument("--expected-version")
    parser.add_argument("--market-limit", type=int, default=25)
    parser.add_argument("--deploy-timeout", type=int, default=0)
    args = parser.parse_args()
    if not 1 <= args.market_limit <= 100:
        parser.error("--market-limit must be between 1 and 100")
    audit = Audit(args.base_url, args.market_limit)
    return asyncio.run(audit.run(args.expected_version, args.deploy_timeout))


if __name__ == "__main__":
    raise SystemExit(main())
