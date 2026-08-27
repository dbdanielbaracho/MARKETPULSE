from __future__ import annotations

import os

import pytest

from app.middleware.home_client_dedup import INTELLIGENCE_RANKING_VERSION
from app.services.discovery_semantics import (
    MIN_BEST_AVAILABLE_VOLUME_USD,
    MIN_DISCOVERY_VOLUME_USD,
    SEMANTIC_DISCOVERY_VERSION,
)

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production thin-activity regression runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")
RAILWAY = os.getenv(
    "PREDIBEACON_RAILWAY_URL",
    "https://marketpulse-production-aa9f.up.railway.app",
)
ESCAPED_TITLE = "Chicago WS wins by over 9.5 runs?"


def _assert_ranked_payload(label: str, response, *, sorted_by_trend: bool) -> None:
    assert response.ok, (label, response.status)
    headers = {key.casefold(): value for key, value in response.headers.items()}
    assert headers.get("x-predibeacon-semantic-discovery") == SEMANTIC_DISCOVERY_VERSION, (
        label,
        headers,
    )
    mode = headers.get("x-predibeacon-discovery-mode")
    assert mode in {"attention", "best-available"}, (label, headers)

    items = response.json()
    assert isinstance(items, list), (label, type(items))
    assert int(headers.get("x-predibeacon-curated-count", "-1")) == len(items), (
        label,
        headers,
        len(items),
    )

    minimum_volume = (
        MIN_BEST_AVAILABLE_VOLUME_USD
        if mode == "best-available"
        else MIN_DISCOVERY_VOLUME_USD
    )
    trends = []
    for item in items:
        volume = item.get("volume_usd")
        confidence = item.get("activity_confidence")
        attention = item.get("attention_score")
        assert isinstance(volume, (int, float)) and not isinstance(volume, bool), (label, item)
        assert volume >= minimum_volume, (label, item.get("canonical_id"), volume, mode)
        assert isinstance(confidence, (int, float)) and 0 <= confidence <= 1, (label, item)
        assert isinstance(attention, (int, float)) and 0 <= attention <= 100, (label, item)
        if volume < 100_000:
            assert confidence < 1, (label, item.get("canonical_id"), volume, confidence)
        trends.append(item.get("trend_score"))

    if sorted_by_trend:
        numeric = [value for value in trends if isinstance(value, (int, float))]
        assert numeric == sorted(numeric, reverse=True), (label, numeric[:20])

    escaped = [item for item in items if item.get("title") == ESCAPED_TITLE]
    assert not escaped, (label, escaped)


def test_real_production_uses_shared_activity_confidence_for_movers_trending_and_top():
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            for label, base in (("custom", CUSTOM), ("railway", RAILWAY)):
                movers = request.get(
                    base + "/api/v1/discovery?venue=kalshi&sort=movers&limit=100",
                    timeout=30_000,
                )
                _assert_ranked_payload(label + ":movers", movers, sorted_by_trend=False)

                trending = request.get(
                    base + "/api/v1/discovery?venue=kalshi&sort=trending&limit=100",
                    timeout=30_000,
                )
                _assert_ranked_payload(label + ":trending", trending, sorted_by_trend=True)

                top = request.get(base + "/top", timeout=30_000)
                assert top.ok, (label, top.status)
                top_headers = {key.casefold(): value for key, value in top.headers.items()}
                assert top_headers.get("x-predibeacon-intelligence-ranking") == INTELLIGENCE_RANKING_VERSION, (
                    label,
                    top_headers,
                )
        finally:
            request.dispose()
