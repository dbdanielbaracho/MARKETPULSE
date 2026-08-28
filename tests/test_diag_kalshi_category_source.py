from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import httpx

BASE = "https://external-api.kalshi.com/trade-api/v2"
TARGETS = {"Politics", "Science and Technology"}


def test_diag_kalshi_category_source() -> None:
    async def get_json(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        delay = 0.5
        for attempt in range(6):
            r = await client.get(f"{BASE}{path}", params=params)
            if r.status_code != 429:
                r.raise_for_status()
                p = r.json() if r.content else {}
                return p if isinstance(p, dict) else {}
            await asyncio.sleep(delay)
            delay *= 2
        r.raise_for_status()
        return {}

    async def run() -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            tags_payload = await get_json(client, "/search/tags_by_categories")
            mapping = tags_payload.get("tags_by_categories", {})
            print("KALSHI_CATEGORY_NAMES", sorted(mapping.keys()) if isinstance(mapping, dict) else [])

            series_payload = await get_json(client, "/series", {"include_volume": "true"})
            series_rows = series_payload.get("series", [])
            if not isinstance(series_rows, list): series_rows = []
            counts = Counter(str(x.get("category") or "") for x in series_rows if isinstance(x, dict))
            print("KALSHI_SERIES_CATEGORY_COUNTS", dict(counts))
            for target in TARGETS:
                rows = [x for x in series_rows if isinstance(x, dict) and str(x.get("category") or "") == target]
                print(f"TARGET_SERIES {target} count={len(rows)}")
                for x in sorted(rows, key=lambda r: float(r.get("volume_fp") or 0), reverse=True)[:15]:
                    print({"series_ticker": x.get("ticker"), "title": x.get("title"), "category": x.get("category"), "volume_fp": x.get("volume_fp"), "tags": x.get("tags")})

            # Fetch all open events once; event objects carry category and nested markets.
            open_events: list[dict[str, Any]] = []
            cursor: str | None = None
            while True:
                params: dict[str, Any] = {"status": "open", "with_nested_markets": "true", "limit": 200}
                if cursor: params["cursor"] = cursor
                p = await get_json(client, "/events", params)
                page = p.get("events", [])
                if isinstance(page, list): open_events.extend(e for e in page if isinstance(e, dict))
                nxt = str(p.get("cursor") or "").strip() or None
                if not nxt or nxt == cursor: break
                cursor = nxt
                await asyncio.sleep(0.15)

            event_counts = Counter(str(e.get("category") or "") for e in open_events)
            print("OPEN_EVENT_CATEGORY_COUNTS", dict(event_counts))
            target_markets: dict[str, list[dict[str, Any]]] = {target: [] for target in TARGETS}
            for target in TARGETS:
                events = [e for e in open_events if str(e.get("category") or "") == target]
                for e in events:
                    markets = e.get("markets")
                    if isinstance(markets, list): target_markets[target].extend(m for m in markets if isinstance(m, dict))
                print(f"OPEN_EVENTS {target} count={len(events)} OPEN_MARKETS {target} count={len(target_markets[target])}")

            # Exact provider pool currently scanned by PrediBeacon.
            pool: list[dict[str, Any]] = []
            cursor = None
            while len(pool) < 5000:
                params = {"limit": min(1000, 5000-len(pool)), "status": "open", "mve_filter": "exclude"}
                if cursor: params["cursor"] = cursor
                p = await get_json(client, "/markets", params)
                page = p.get("markets", [])
                if isinstance(page, list): pool.extend(m for m in page if isinstance(m, dict))
                nxt = str(p.get("cursor") or "").strip() or None
                if not nxt or nxt == cursor: break
                cursor = nxt
                await asyncio.sleep(0.15)
            pool_tickers = {str(x.get("ticker") or "") for x in pool}
            print("OPEN_MARKET_POOL_COUNT", len(pool))

            for target, markets in target_markets.items():
                tickers = [str(x.get("ticker") or "") for x in markets if str(x.get("ticker") or "")]
                overlap = [t for t in tickers if t in pool_tickers]
                print(f"OVERLAP {target} target_markets={len(tickers)} in_first_5000={len(overlap)} outside_first_5000={len(tickers)-len(overlap)}")
                def vol24(x: dict[str, Any]) -> float:
                    try: return float(x.get("volume_24h_fp") or 0)
                    except Exception: return 0.0
                for x in sorted(markets, key=vol24, reverse=True)[:25]:
                    print({"category": target, "ticker": x.get("ticker"), "title": x.get("title"), "event_ticker": x.get("event_ticker"), "volume_24h_fp": x.get("volume_24h_fp"), "volume_fp": x.get("volume_fp"), "close_time": x.get("close_time"), "in_first_5000": str(x.get("ticker") or "") in pool_tickers})

        assert False, "temporary Kalshi category-source diagnostic complete"

    asyncio.run(run())
