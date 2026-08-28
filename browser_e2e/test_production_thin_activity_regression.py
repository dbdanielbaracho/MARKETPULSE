from __future__ import annotations

import os

import pytest

from app.middleware.home_client_dedup import INTELLIGENCE_RANKING_VERSION
from app.services.discovery_semantics import (
    MIN_BEST_AVAILABLE_VOLUME_USD,
    MIN_DISCOVERY_VOLUME_USD,
    SEMANTIC_DISCOVERY_VERSION,
    evaluate_discovery_market,
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


def _pool_snapshot(request, base: str, venue: str, sort: str) -> dict[str, object]:
    raw = request.get(
        base + f"/api/v1/markets?venue={venue}&sort={sort}&limit=100",
        timeout=30_000,
    )
    payload = raw.json() if raw.ok else []
    if not isinstance(payload, list):
        payload = []

    sample = []
    reason_counts: dict[str, int] = {}
    volumes: list[float] = []
    best_available_eligible = 0
    strict_eligible = 0
    for item in payload:
        decision = evaluate_discovery_market(item)
        reason_counts[decision.reason_code] = reason_counts.get(decision.reason_code, 0) + 1
        volume = item.get("volume_usd")
        numeric_volume = float(volume) if isinstance(volume, (int, float)) and not isinstance(volume, bool) else 0.0
        volumes.append(numeric_volume)
        if decision.eligible:
            strict_eligible += 1
        if (
            decision.reason_code != "invalid_market"
            and numeric_volume >= MIN_BEST_AVAILABLE_VOLUME_USD
            and decision.relevance >= 12
        ):
            best_available_eligible += 1
        if len(sample) < 8:
            sample.append(
                {
                    "canonical_id": item.get("canonical_id"),
                    "title": item.get("title"),
                    "category": item.get("category"),
                    "volume_usd": item.get("volume_usd"),
                    "trend_score": item.get("trend_score"),
                    "probability_change": item.get("probability_change"),
                    "closes_at": item.get("closes_at"),
                    "eligible": decision.eligible,
                    "relevance": decision.relevance,
                    "reason_code": decision.reason_code,
                }
            )

    discovery = request.get(
        base + f"/api/v1/discovery?venue={venue}&sort={sort}&limit=100",
        timeout=30_000,
    )
    discovery_items = discovery.json() if discovery.ok else []
    if not isinstance(discovery_items, list):
        discovery_items = []
    discovery_headers = {key.casefold(): value for key, value in discovery.headers.items()}

    return {
        "sort": sort,
        "inventory_status": raw.status,
        "inventory_count": len(payload),
        "max_volume_usd": max(volumes, default=0.0),
        "count_volume_gte_500": sum(1 for value in volumes if value >= MIN_BEST_AVAILABLE_VOLUME_USD),
        "count_volume_gte_1000": sum(1 for value in volumes if value >= MIN_DISCOVERY_VOLUME_USD),
        "strict_eligible": strict_eligible,
        "best_available_eligible": best_available_eligible,
        "reason_counts": reason_counts,
        "discovery_count": len(discovery_items),
        "discovery_mode": discovery_headers.get("x-predibeacon-discovery-mode"),
        "monitored_candidate_count": discovery_headers.get("x-predibeacon-monitored-candidate-count"),
        "category_coverage": discovery_headers.get("x-predibeacon-category-coverage"),
        "sample": sample,
    }


def _diagnose_empty(request, base: str, venue: str) -> dict[str, object]:
    return {
        sort: _pool_snapshot(request, base, venue, sort)
        for sort in ("movers", "volume", "trending")
    }


def _assert_ranked_payload(
    label: str,
    response,
    *,
    sort: str,
    request,
    base: str,
    venue: str,
) -> list[dict[str, object]]:
    assert response.ok, (label, response.status)
    headers = {key.casefold(): value for key, value in response.headers.items()}
    assert headers.get("x-predibeacon-semantic-discovery") == SEMANTIC_DISCOVERY_VERSION, (
        label,
        headers,
    )
    mode = headers.get("x-predibeacon-discovery-mode")
    assert mode in {"attention", "best-available"}, (label, headers)
    assert "x-predibeacon-category-coverage" in headers, (label, headers)

    items = response.json()
    assert isinstance(items, list), (label, type(items))
    if not items:
        diagnostics = _diagnose_empty(request, base, venue)
        pytest.fail(
            f"{label}: expected at least one real production Discovery card; "
            f"headers={headers}; pool_diagnostics={diagnostics}"
        )
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
        if sort == "movers":
            change = item.get("probability_change")
            assert isinstance(change, (int, float)) and abs(change) >= 0.0005, (label, item)

    escaped = [item for item in items if item.get("title") == ESCAPED_TITLE]
    assert not escaped, (label, escaped)
    return items


def _assert_kalshi_category_visible(request, base: str, category: str) -> None:
    response = request.get(
        base + f"/api/v1/discovery?venue=kalshi&category={category}&sort=trending&limit=50",
        timeout=30_000,
    )
    label = f"kalshi:{category}"
    items = _assert_ranked_payload(
        label,
        response,
        sort="trending",
        request=request,
        base=base,
        venue="kalshi",
    )
    assert all(item.get("category") == category for item in items), (label, items[:10])


def test_real_production_has_ranked_cards_for_each_supported_venue_and_kalshi_categories():
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            for label, base in (("custom", CUSTOM), ("railway", RAILWAY)):
                for venue in ("kalshi", "polymarket"):
                    movers = request.get(
                        base + f"/api/v1/discovery?venue={venue}&sort=movers&limit=100",
                        timeout=30_000,
                    )
                    _assert_ranked_payload(
                        label + f":{venue}:movers",
                        movers,
                        sort="movers",
                        request=request,
                        base=base,
                        venue=venue,
                    )

                    trending = request.get(
                        base + f"/api/v1/discovery?venue={venue}&sort=trending&limit=100",
                        timeout=30_000,
                    )
                    _assert_ranked_payload(
                        label + f":{venue}:trending",
                        trending,
                        sort="trending",
                        request=request,
                        base=base,
                        venue=venue,
                    )

                # This is the production truth gate for the incident that exposed
                # the global Kalshi cursor bias. If Kalshi currently publishes
                # valid category markets, Politics and Tech must reach Discovery.
                _assert_kalshi_category_visible(request, base, "Politics")
                _assert_kalshi_category_visible(request, base, "Tech")

                top = request.get(base + "/top", timeout=30_000)
                assert top.ok, (label, top.status)
                top_headers = {key.casefold(): value for key, value in top.headers.items()}
                assert top_headers.get("x-predibeacon-intelligence-ranking") == INTELLIGENCE_RANKING_VERSION, (
                    label,
                    top_headers,
                )
        finally:
            request.dispose()
