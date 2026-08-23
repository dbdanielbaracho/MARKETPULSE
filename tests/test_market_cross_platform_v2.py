from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_contract_verification as verification_routes
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.entrypoint import app
from app.services.market_page_enhancements import enhance_market_template


client = TestClient(app)


def _seed_pair(*, counterpart_title: str = "Does candidate X win the 2026 election?") -> None:
    now = datetime.now(timezone.utc)
    closes = datetime(2026, 11, 3, 20, tzinfo=timezone.utc)
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id="kalshi:KXTARGET",
            title="Will candidate X win the 2026 election?",
            venue="kalshi",
            category="Politics",
            probability=.58,
            trend_score=80,
            observed_at=now,
            closes_at=closes,
        ),
        core.DiscoveryMarket(
            canonical_id="polymarket:900",
            title=counterpart_title,
            venue="polymarket",
            category="Politics",
            probability=.62,
            trend_score=82,
            observed_at=now,
            closes_at=closes,
        ),
    ])
    verification_routes._FACT_CACHE.clear()


def test_targeted_cross_platform_endpoint_verifies_non_identical_titles(monkeypatch):
    _seed_pair()

    async def fake_kalshi(self, ticker):
        return {"market": {
            "title": "Will candidate X win the 2026 election?",
            "close_time": "2026-11-03T20:00:00Z",
            "resolution_source": "https://apnews.com/elections",
            "rules_primary": "The Associated Press race call determines the winner of the 2026 election.",
        }}

    async def fake_poly(self, market_id):
        return {
            "question": "Will candidate X win the 2026 election?",
            "endDate": "2026-11-03T21:00:00Z",
            "resolutionSource": "https://www.apnews.com/elections",
            "description": "This market resolves based on the Associated Press race call for the 2026 election winner.",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)
    response = client.get("/api/v1/market/cross-platform", params={"market_id": "kalshi:KXTARGET"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["counterpart"]["canonical_id"] == "polymarket:900"
    assert payload["verification"]["equivalent_contracts"] is True
    assert payload["verification"]["consensus_probability"] == .6
    assert payload["verification"]["gap_points"] == 4
    assert payload["candidate_score"] > 70
    assert response.headers["cache-control"].startswith("public, max-age=60")


def test_targeted_endpoint_rejects_conflicting_numeric_anchor_without_external_calls(monkeypatch):
    _seed_pair(counterpart_title="Will candidate X win the 2028 election?")
    calls = 0

    async def should_not_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("conflicting anchors must fail candidate discovery before external calls")

    monkeypatch.setattr(KalshiAdapter, "fetch_market", should_not_call)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", should_not_call)
    response = client.get("/api/v1/market/cross-platform", params={"market_id": "kalshi:KXTARGET"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["counterpart"] is None
    assert payload["verification"] is None
    assert payload["candidates_checked"] == 0
    assert calls == 0


def test_market_detail_enhancer_replaces_legacy_exact_title_call():
    source = (
        '<section class="panel"><div class="eyebrow">CROSS-PLATFORM CHECK</div>'
        '<script>updateQuality();loadCrossPlatform();async function loadSignals(){}loadMarket();loadSignals();</script>'
    )
    enhanced = enhance_market_template(source)
    assert "loadCrossPlatformV2()" in enhanced
    assert "/api/v1/market/cross-platform?" in enhanced
    assert "will not substitute title-only matching" in enhanced
    assert "updateQuality();loadCrossPlatform()" not in enhanced


def test_rendered_market_page_uses_cross_platform_v2():
    _seed_pair()
    response = client.get("/market", params={"market_id": "kalshi:KXTARGET"})
    assert response.status_code == 200
    assert "/api/v1/market/cross-platform?" in response.text
    assert "loadCrossPlatformV2()" in response.text
    assert "Contract verification confidence" in response.text


def test_targeted_cross_platform_endpoint_is_registered():
    assert "/api/v1/market/cross-platform" in app.openapi()["paths"]
