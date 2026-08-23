from __future__ import annotations

from fastapi import APIRouter, Depends, Query

import app.main as core
from app.storage.revenue import RevenueStore
from app.storage.traffic import TrafficStore


router = APIRouter(prefix="/api/v1/admin", tags=["admin-traffic"])


@router.get("/traffic", dependencies=[Depends(core._require_admin)])
def traffic_summary(
    days: int = Query(default=30, ge=1, le=365),
    top_markets: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    traffic = TrafficStore(core._database_path()).summary(days=days, top_markets=top_markets)
    revenue = RevenueStore(core._database_path()).summary()
    home_views = int(traffic["views_by_surface"].get("home", 0))
    market_views = int(traffic["views_by_surface"].get("market", 0))
    outbound_clicks = int(revenue["click_context_count"])
    return {
        **traffic,
        "funnel": {
            "home_views": home_views,
            "market_detail_views": market_views,
            "outbound_clicks": outbound_clicks,
            "home_to_market_rate": round(market_views / home_views, 4) if home_views else None,
            "market_to_outbound_rate": round(outbound_clicks / market_views, 4) if market_views else None,
        },
        "outbound_clicks_by_channel": revenue["clicks_by_channel"],
        "notice": "Page views are aggregate first-party counts. Outbound clicks come from the durable partner-attribution ledger.",
    }
