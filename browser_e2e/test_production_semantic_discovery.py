from __future__ import annotations

import os

import pytest

from app.services.discovery_semantics import (
    MIN_DISCOVERY_RELEVANCE_SCORE,
    MIN_DISCOVERY_VOLUME_USD,
    SEMANTIC_DISCOVERY_VERSION,
)

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="semantic production truth gate runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")
RAILWAY = os.getenv(
    "PREDIBEACON_RAILWAY_URL",
    "https://marketpulse-production-aa9f.up.railway.app",
)


def _assert_semantic_payload(label: str, response) -> list[dict]:
    assert response.ok, (label, response.status)
    headers = {key.casefold(): value for key, value in response.headers.items()}
    assert headers.get("x-predibeacon-semantic-discovery") == SEMANTIC_DISCOVERY_VERSION, (label, headers)
    items = response.json()
    assert isinstance(items, list), (label, type(items))
    for item in items:
        assert item.get("semantic_discovery_version") == SEMANTIC_DISCOVERY_VERSION, (label, item)
        assert (item.get("volume_usd") or 0) >= MIN_DISCOVERY_VOLUME_USD, (label, item)
        assert (item.get("relevance_score") or 0) >= MIN_DISCOVERY_RELEVANCE_SCORE, (label, item)
        assert item.get("attention_reason_code") in {
            "sharp_move_with_activity",
            "closing_soon",
            "high_activity",
            "meaningful_move",
            "high_relevance",
            "balanced_signal",
        }, (label, item)
    return items


def test_real_production_discovery_only_highlights_semantically_eligible_markets():
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            for label, base in (("custom", CUSTOM), ("railway", RAILWAY)):
                for venue in ("kalshi", "polymarket"):
                    for sort in ("trending", "movers", "volume"):
                        response = request.get(
                            base + f"/api/v1/markets?venue={venue}&sort={sort}&limit=100",
                            timeout=30_000,
                        )
                        _assert_semantic_payload(f"{label}:{venue}:{sort}", response)
        finally:
            request.dispose()


def test_real_portuguese_kalshi_journey_has_semantic_empty_state_or_localized_reasons():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            page.goto(
                CUSTOM + "/set-language?lang=pt-BR&next=%2F%3Fvenue%3Dkalshi%23markets",
                wait_until="networkidle",
                timeout=45_000,
            )
            page.wait_for_timeout(500)
            cards = page.locator("#grid .card")
            count = cards.count()
            if count == 0:
                state = page.locator("#state").inner_text().casefold()
                assert "critérios documentados de atenção" in state, state
            else:
                forbidden_english = (
                    "This contract closes within 72 hours",
                    "A large recent probability move pushed this market up the ranking",
                    "High reported activity makes this market worth monitoring",
                    "Ranked using movement, activity, freshness and availability",
                )
                for index in range(count):
                    insight = cards.nth(index).locator(".insight").inner_text()
                    assert not any(phrase in insight for phrase in forbidden_english), insight
                    assert "Por que importa" in insight, insight
        finally:
            browser.close()
