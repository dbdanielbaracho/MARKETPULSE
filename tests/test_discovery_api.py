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


def test_equal_scores_are_balanced_across_venues():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id=f"kalshi:{index}", title=f"Kalshi {index}", venue="kalshi", probability=.5, volume_usd=100, trend_score=30, observed_at=now)
        for index in range(3)
    ] + [
        DiscoveryMarket(canonical_id=f"polymarket:{index}", title=f"Polymarket {index}", venue="polymarket", probability=.5, volume_usd=100, trend_score=30, observed_at=now)
        for index in range(3)
    ])
    data = client.get("/api/v1/markets?sort=trending&limit=4").json()
    assert [item["venue"] for item in data] == ["kalshi", "polymarket", "kalshi", "polymarket"]


def test_venue_filter_returns_requested_platform_only():
    seed()
    data = client.get("/api/v1/markets?venue=kalshi").json()
    assert len(data) == 2
    assert {item["venue"] for item in data} == {"kalshi"}


def test_invalid_venue_is_rejected():
    assert client.get("/api/v1/markets?venue=unknown").status_code == 422


def test_comparison_never_equates_same_title_with_different_deadline():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:x", title="Will X happen?", venue="kalshi", probability=.5, volume_usd=1, trend_score=1, observed_at=now, closes_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        DiscoveryMarket(canonical_id="polymarket:x", title="Will X happen?", venue="polymarket", probability=.5, volume_usd=1, trend_score=1, observed_at=now, closes_at=datetime(2026, 9, 2, tzinfo=timezone.utc)),
    ])
    result = client.get("/api/v1/compare", params={"left_id": "kalshi:x", "right_id": "polymarket:x"})
    assert result.status_code == 200
    assert result.json()["decision"] == "not_equivalent"
    assert result.json()["equivalent_contracts"] is False


def test_comparison_fails_closed_when_rules_are_unavailable():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:y", title="Will Y happen?", venue="kalshi", probability=.5, volume_usd=1, trend_score=1, observed_at=now),
        DiscoveryMarket(canonical_id="polymarket:y", title="Will Y happen?", venue="polymarket", probability=.5, volume_usd=1, trend_score=1, observed_at=now),
    ])
    data = client.get("/api/v1/compare", params={"left_id": "kalshi:y", "right_id": "polymarket:y"}).json()
    assert data["decision"] == "insufficient_evidence"
    assert data["equivalent_contracts"] is False
    assert "require matching" in data["warning"].lower()


def test_comparison_returns_404_for_unknown_market():
    seed()
    response = client.get("/api/v1/compare", params={"left_id": "kalshi:a", "right_id": "kalshi:missing"})
    assert response.status_code == 404


def test_market_evidence_preserves_primary_venue_provenance():
    now = datetime.now(timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:evidence",
            title="Will evidence remain attributable?",
            venue="kalshi",
            probability=.5,
            volume_usd=1,
            trend_score=1,
            observed_at=now,
            source_url="https://kalshi.com/markets/evidence",
        )
    ])
    response = client.get("/api/v1/evidence", params={"market_id": "kalshi:evidence"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["publisher_count"] == 1
    assert payload["items"][0]["publisher"] == "Kalshi"
    assert payload["items"][0]["kind"] == "venue"
    assert payload["items"][0]["freshness"] == "undated"
    assert payload["items"][0]["url"] == "https://kalshi.com/markets/evidence"


def test_market_evidence_returns_404_for_unknown_market():
    set_discovery_markets([])
    assert client.get("/api/v1/evidence", params={"market_id": "missing"}).status_code == 404


def test_market_evidence_bounds_long_venue_titles():
    now = datetime.now(timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:long",
            title="Long combined contract " + ("selection, " * 60),
            venue="kalshi",
            probability=.5,
            volume_usd=1,
            trend_score=1,
            observed_at=now,
            source_url="https://kalshi.com/markets/long",
        )
    ])
    response = client.get("/api/v1/evidence", params={"market_id": "kalshi:long"})
    assert response.status_code == 200
    assert len(response.json()["items"][0]["title"]) <= 300


def test_market_evidence_combines_primary_and_official_sources(monkeypatch):
    import app.main as main
    from app.domain.evidence import EvidenceItem, EvidenceKind

    now = datetime.now(timezone.utc)
    market = DiscoveryMarket(
        canonical_id="kalshi:fed",
        title="Federal Reserve monetary policy decision",
        venue="kalshi",
        probability=.5,
        volume_usd=1,
        trend_score=1,
        observed_at=now,
        source_url="https://kalshi.com/markets/fed",
    )
    official = EvidenceItem(
        title="Federal Reserve issues monetary policy statement",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary.htm",
        publisher="Federal Reserve",
        kind=EvidenceKind.OFFICIAL,
        published_at=now,
        retrieved_at=now,
    )
    set_discovery_markets([market])
    monkeypatch.setattr(main, "_EXTERNAL_EVIDENCE", {market.canonical_id: [official]})
    payload = client.get("/api/v1/evidence", params={"market_id": market.canonical_id}).json()
    assert payload["publisher_count"] == 2
    assert {item["kind"] for item in payload["items"]} == {"venue", "official"}
