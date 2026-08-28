from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import httpx

BASE = "https://external-api.kalshi.com/trade-api/v2"


def test_diag_kalshi_category_source() -> None:
    async def run() -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1) Discover the exact category names Kalshi exposes.
            tags_resp = await client.get(f"{BASE}/search/tags_by_categories")
            tags_resp.raise_for_status()
            tags_payload = tags_resp.json() if tags_resp.content else {}
            mapping = tags_payload.get("tags_by_categories", {}) if isinstance(tags_payload, dict) else {}
            category_names = sorted(str(k) for k in mapping.keys()) if isinstance(mapping, dict) else []
            print("KALSHI_CATEGORY_NAMES", category_names)

            # 2) Fetch all series and classify target category names case-insensitively.
            series_resp = await client.get(f"{BASE}/series", params={"include_volume": "true"})
            series_resp.raise_for_status()
            series_payload = series_resp.json() if series_resp.content else {}
            series_rows = series_payload.get("series", []) if isinstance(series_payload, dict) else []
            if not isinstance(series_rows, list):
                series_rows = []
            counts = Counter(str(x.get("category") or "") for x in series_rows if isinstance(x, dict))
            print("KALSHI_SERIES_CATEGORY_COUNTS", dict(counts))

            target_series: dict[str, list[dict[str, Any]]] = {"politics": [], "technology": []}
            for item in series_rows:
                if not isinstance(item, dict):
                    continue
                cat = str(item.get("category") or "").strip().lower()
                if cat == "politics":
                    target_series["politics"].append(item)
                if cat in {"technology", "tech"}:
                    target_series["technology"].append(item)

            for key, items in target_series.items():
                print(f"TARGET_SERIES {key} count={len(items)}")
                for x in sorted(items, key=lambda r: float(r.get("volume_fp") or 0), reverse=True)[:25]:
                    print({"ticker": x.get("ticker"), "title": x.get("title"), "category": x.get("category"), "volume_fp": x.get("volume_fp"), "tags": x.get("tags")})

            # 3) Resolve open events + nested markets for every target series.
            sem = asyncio.Semaphore(15)
            async def events_for_series(series_ticker: str) -> list[dict[str, Any]]:
                out: list[dict[str, Any]] = []
                cursor: str | None = None
                while True:
                    params: dict[str, Any] = {"series_ticker": series_ticker, "status": "open", "with_nested_markets": "true", "limit": 200}
                    if cursor:
                        params["cursor"] = cursor
                    async with sem:
                        r = await client.get(f"{BASE}/events", params=params)
                        r.raise_for_status()
                    p = r.json() if r.content else {}
                    events = p.get("events", []) if isinstance(p, dict) else []
                    if isinstance(events, list):
                        out.extend(e for e in events if isinstance(e, dict))
                    nxt = str(p.get("cursor") or "").strip() or None if isinstance(p, dict) else None
                    if not nxt or nxt == cursor:
                        break
                    cursor = nxt
                return out

            event_results: dict[str, list[dict[str, Any]]] = {"politics": [], "technology": []}
            tasks = []
            task_meta = []
            for cat, items in target_series.items():
                for x in items:
                    ticker = str(x.get("ticker") or "").strip()
                    if ticker:
                        task_meta.append((cat, ticker))
                        tasks.append(events_for_series(ticker))
            resolved = await asyncio.gather(*tasks) if tasks else []
            for (cat, _ticker), events in zip(task_meta, resolved):
                event_results[cat].extend(events)

            target_market_rows: dict[str, list[dict[str, Any]]] = {"politics": [], "technology": []}
            for cat, events in event_results.items():
                for event in events:
                    markets = event.get("markets")
                    if isinstance(markets, list):
                        target_market_rows[cat].extend(m for m in markets if isinstance(m, dict))
                print(f"OPEN_EVENTS {cat} count={len(events)} OPEN_MARKETS {cat} count={len(target_market_rows[cat])}")

            # 4) Fetch the exact first 5,000 open markets used by PrediBeacon and compare ticker intersection.
            pool: list[dict[str, Any]] = []
            cursor: str | None = None
            while len(pool) < 5000:
                params: dict[str, Any] = {"limit": min(1000, 5000-len(pool)), "status": "open", "mve_filter": "exclude"}
                if cursor:
                    params["cursor"] = cursor
                r = await client.get(f"{BASE}/markets", params=params)
                r.raise_for_status()
                p = r.json() if r.content else {}
                page = p.get("markets", []) if isinstance(p, dict) else []
                if isinstance(page, list):
                    pool.extend(m for m in page if isinstance(m, dict))
                nxt = str(p.get("cursor") or "").strip() or None if isinstance(p, dict) else None
                if not nxt or nxt == cursor:
                    break
                cursor = nxt
            pool_tickers = {str(x.get("ticker") or "") for x in pool}
            print("OPEN_MARKET_POOL_COUNT", len(pool))

            for cat, markets in target_market_rows.items():
                tickers = [str(x.get("ticker") or "") for x in markets if str(x.get("ticker") or "")]
                overlap = [t for t in tickers if t in pool_tickers]
                print(f"OVERLAP {cat} target_markets={len(tickers)} in_first_5000={len(overlap)} outside_first_5000={len(tickers)-len(overlap)}")
                # show the most active sample based on provider fields
                def vol24(x: dict[str, Any]) -> float:
                    raw = x.get("volume_24h_fp")
                    try: return float(raw or 0)
                    except Exception: return 0.0
                for x in sorted(markets, key=vol24, reverse=True)[:30]:
                    print({"category": cat, "ticker": x.get("ticker"), "title": x.get("title"), "event_ticker": x.get("event_ticker"), "volume_24h_fp": x.get("volume_24h_fp"), "volume_fp": x.get("volume_fp"), "close_time": x.get("close_time"), "in_first_5000": str(x.get("ticker") or "") in pool_tickers})

        assert False, "temporary Kalshi category-source diagnostic complete"

    asyncio.run(run())
