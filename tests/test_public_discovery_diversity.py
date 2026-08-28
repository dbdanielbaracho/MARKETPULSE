from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import DiscoveryMarket, set_discovery_markets
from app.routes.public_discovery import _soft_category_diversity, router

NOW = datetime.now(timezone.utc)


def _market(identifier: str, title: str, *, category: str, change: float, volume: float = 5000, trend: float = 70) -> DiscoveryMarket:
    return DiscoveryMarket(
        canonical_id=identifier,
        title=title,
        venue="kalshi",
        category=category,
        probability=0.5,
        probability_change=change,
        volume_usd=volume,
        trend_score=trend,
        observed_at=NOW,
        closes_at=NOW + timedelta(days=3),
        source_url="https://kalshi.com/markets/example",
    )


def _client() -> TestClient:
    api = FastAPI()
    api.include_router(router)
    return TestClient(api)


def test_movers_excludes_zero_and_subdisplay_probability_changes():
    set_discovery_markets([
        _market("k:zero", "Zero move but active", category="Sports", change=0.0, volume=50_000),
        _market("k:tiny", "Tiny move", category="Sports", change=0.0004, volume=40_000),
        _market("k:real", "Real mover", category="Politics", change=0.02, volume=10_000),
    ])
    response = _client().get("/api/v1/discovery?venue=kalshi&sort=movers&limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert [item["canonical_id"] for item in payload] == ["k:real"]
    assert all(abs(item["probability_change"]) >= 0.0005 for item in payload)


def test_discovery_exposes_machine_readable_category_coverage():
    set_discovery_markets([
        _market("k:politics", "Politics signal", category="Politics", change=0.03, volume=20_000),
        _market("k:tech", "Tech signal", category="Tech", change=0.025, volume=18_000),
    ])
    response = _client().get("/api/v1/discovery?venue=kalshi&sort=trending&limit=20")
    assert response.status_code == 200
    coverage = response.headers["x-predibeacon-category-coverage"]
    assert "Politics:1" in coverage
    assert "Tech:1" in coverage


def test_soft_diversity_breaks_only_long_near_tied_category_streaks():
    sports = [
        {"canonical_id": f"s:{i}", "category": "Sports", "probability_change": 0.10 - i * 0.001, "attention_score": 90 - i, "volume_usd": 10000}
        for i in range(5)
    ]
    politics = {"canonical_id": "p:1", "category": "Politics", "probability_change": 0.09, "attention_score": 86, "volume_usd": 9000}
    ranked = [*sports, politics]
    result = _soft_category_diversity(ranked, sort="movers", limit=6)
    assert [item["category"] for item in result[:5]] == ["Sports", "Sports", "Sports", "Sports", "Politics"]


def test_soft_diversity_does_not_promote_materially_weaker_category():
    sports = [
        {"canonical_id": f"s:{i}", "category": "Sports", "probability_change": 0.10, "attention_score": 90, "volume_usd": 10000}
        for i in range(5)
    ]
    weak_tech = {"canonical_id": "t:1", "category": "Tech", "probability_change": 0.03, "attention_score": 50, "volume_usd": 1000}
    result = _soft_category_diversity([*sports, weak_tech], sort="movers", limit=6)
    assert [item["category"] for item in result[:5]] == ["Sports"] * 5
