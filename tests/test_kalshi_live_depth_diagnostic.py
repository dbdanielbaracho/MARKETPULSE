from __future__ import annotations

import json

import httpx
import pytest

from app.adapters.kalshi import KalshiAdapter


@pytest.mark.parametrize(
    "base_url",
    [
        "https://external-api.kalshi.com/trade-api/v2",
        "https://api.elections.kalshi.com/trade-api/v2",
    ],
)
def test_live_kalshi_market_depth_diagnostic(base_url: str) -> None:
    client = httpx.Client(timeout=30.0)
    cursor = None
    scanned = 0
    page_stats = []
    active_examples = []
    try:
        for page_number in range(1, 6):
            params = {"limit": 1000, "status": "open", "mve_filter": "exclude"}
            if cursor:
                params["cursor"] = cursor
            response = client.get(base_url + "/markets", params=params)
            response.raise_for_status()
            payload = response.json()
            markets = payload.get("markets", []) if isinstance(payload, dict) else []
            markets = markets if isinstance(markets, list) else []
            scanned += len(markets)
            volumes = []
            volumes_24h = []
            for item in markets:
                if not isinstance(item, dict):
                    continue
                volume = KalshiAdapter._usd_notional_volume(item) or 0.0
                volume_24h = KalshiAdapter._usd_notional_volume_24h(item) or 0.0
                volumes.append(volume)
                volumes_24h.append(volume_24h)
                if (volume >= 500 or volume_24h > 0) and len(active_examples) < 12:
                    active_examples.append({
                        "ticker": item.get("ticker"),
                        "title": item.get("title"),
                        "volume_usd": volume,
                        "volume_24h_usd": volume_24h,
                        "close_time": item.get("close_time"),
                    })
            page_stats.append({
                "page": page_number,
                "count": len(markets),
                "max_volume_usd": max(volumes, default=0.0),
                "max_volume_24h_usd": max(volumes_24h, default=0.0),
                "count_volume_gte_500": sum(value >= 500 for value in volumes),
                "count_24h_positive": sum(value > 0 for value in volumes_24h),
            })
            cursor = str(payload.get("cursor") or "").strip() or None
            if not cursor:
                break

        trades_response = client.get(base_url + "/markets/trades", params={"limit": 1000})
        trades_status = trades_response.status_code
        trades = []
        if trades_response.is_success:
            trades_payload = trades_response.json()
            trades = trades_payload.get("trades", []) if isinstance(trades_payload, dict) else []
            trades = trades if isinstance(trades, list) else []
        trade_tickers = []
        for trade in trades:
            if isinstance(trade, dict):
                ticker = str(trade.get("ticker") or "").strip()
                if ticker and ticker not in trade_tickers:
                    trade_tickers.append(ticker)
                if len(trade_tickers) >= 20:
                    break

        report = {
            "base_url": base_url,
            "scanned_open_markets": scanned,
            "pages": page_stats,
            "active_examples": active_examples,
            "trades_status": trades_status,
            "trade_count": len(trades),
            "recent_trade_tickers": trade_tickers,
        }
        pytest.fail("KALSHI_LIVE_DEPTH_DIAGNOSTIC=" + json.dumps(report, sort_keys=True))
    finally:
        client.close()
