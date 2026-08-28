from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import httpx

from app.adapters.kalshi import KalshiAdapter
from app.services.categories import classify_market_category

BASE = "https://api.elections.kalshi.com/trade-api/v2"


def _activity(item: dict[str, Any]) -> tuple[float, float]:
    return KalshiAdapter._activity_rank_key(item)


def test_diag_kalshi_politics_tech_inventory() -> None:
    async def run() -> None:
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(rows) < 5000:
                params: dict[str, Any] = {"limit": min(1000, 5000-len(rows)), "status": "open", "mve_filter": "exclude"}
                if cursor:
                    params["cursor"] = cursor
                r = await client.get(f"{BASE}/markets", params=params)
                r.raise_for_status()
                p = r.json()
                page = p.get("markets", []) if isinstance(p, dict) else []
                if not isinstance(page, list): page = []
                rows.extend(x for x in page if isinstance(x, dict))
                nxt = str(p.get("cursor") or "").strip() or None
                if not nxt or nxt == cursor: break
                cursor = nxt

            series = sorted({str(x.get("series_ticker") or "").strip() for x in rows if str(x.get("series_ticker") or "").strip()})
            sem = asyncio.Semaphore(20)
            meta: dict[str, str] = {}
            async def resolve(s: str) -> None:
                try:
                    async with sem:
                        r = await client.get(f"{BASE}/series/{s}")
                        r.raise_for_status()
                    p = r.json(); obj = p.get("series", {}) if isinstance(p, dict) else {}
                    if isinstance(obj, dict): meta[s] = str(obj.get("category") or "").strip()
                except Exception:
                    pass
            await asyncio.gather(*(resolve(s) for s in series))

        ranked = sorted(rows, key=_activity, reverse=True)
        out = []
        for provider_rank, x in enumerate(ranked, 1):
            st = str(x.get("series_ticker") or "").strip()
            provider_cat = meta.get(st) or x.get("category")
            title = str(x.get("title") or x.get("subtitle") or x.get("ticker") or "")
            cat = classify_market_category(title=title, provider_category=provider_cat, raw=x)
            if cat in {"politics", "technology"} or str(provider_cat).lower() in {"politics", "technology", "tech"}:
                out.append({"rank": provider_rank, "category": cat, "provider_category": provider_cat, "title": title, "ticker": x.get("ticker"), "volume_24h_usd": KalshiAdapter._usd_notional_volume_24h(x), "volume_usd": KalshiAdapter._usd_notional_volume(x), "close_time": x.get("close_time")})

        counts = Counter(str(x["category"]) for x in out)
        print("KALSHI_POLITICS_TECH_DIAG", {"scanned": len(rows), "series_resolved": len(meta), "counts": dict(counts), "matches": len(out)})
        for cat in ("politics", "technology"):
            items = [x for x in out if x["category"] == cat]
            print(f"CATEGORY {cat} count={len(items)}")
            for x in items[:40]: print(x)
        assert False, "temporary diagnostic complete; inspect printed inventory"

    asyncio.run(run())
