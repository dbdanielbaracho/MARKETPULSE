from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import DiscoveryMarket, app, set_discovery_markets

client = TestClient(app)


def seed() -> None:
    now = datetime(2026, 8, 21, 20, 0, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:a", title="Fed decision", venue="kalshi", category="Economy", probability=.65, probability_change=.12, volume_usd=1000, trend_score=80, observed_at=now),
        DiscoveryMarket(canonical_id="polymarket:b", title="AI launch", venue="polymarket", category="Tech", probability=.40, probability_change=.20, volume_usd=500, trend_score=70, observed_at=now),
        DiscoveryMarket(canonical_id="kalshi:c", title="Inflation report", venue="kalshi", category="Economy", probability=.55, probability_change=None, volume_usd=9000, trend_score=60, observed_at=now),
    ])


def test_trending_sort():
    seed()
    data = client.get("/api/v1/markets?sort=trending").json()
    assert [item["canonical_id"] for item in data] == ["kalshi:a", "polymarket:b", "kalshi:c"]


def test_movers_does_not_fake_missing_change():
    seed()
    data = client.get("/api/v1/markets?sort=movers").json()
    assert data[0]["canonical_id"] == "polymarket:b"
    assert data[-1]["probability_change"] is None


def test_volume_sort_filter_and_search():
    seed()
    data = client.get("/api/v1/markets?sort=volume&category=Economy&q=inflation").json()
    assert len(data) == 1
    assert data[0]["canonical_id"] == "kalshi:c"


def test_limit_is_bounded():
    response = client.get("/api/v1/markets?limit=101")
    assert response.status_code == 422
