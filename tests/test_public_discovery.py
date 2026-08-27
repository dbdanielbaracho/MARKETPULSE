from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import DiscoveryMarket, set_discovery_markets
from app.routes.public_discovery import router
from app.services.discovery_semantics import (
    MIN_DISCOVERY_RELEVANCE_SCORE,
    MIN_DISCOVERY_VOLUME_USD,
    SEMANTIC_DISCOVERY_VERSION,
)

NOW = datetime.now(timezone.utc)


def _client() -> TestClient:
    api = FastAPI()
    api.include_router(router)
    return TestClient(api)


def _market(identifier: str, title: str, *, volume: float, trend: float, change: float = 0.04) -> DiscoveryMarket:
    return DiscoveryMarket(
        canonical_id=identifier,
        title=title,
        venue="kalshi",
        probability=0.5,
        probability_change=change,
        volume_usd=volume,
        trend_score=trend,
        observed_at=NOW,
        closes_at=NOW + timedelta(days=2),
        source_url="https://kalshi.com/markets/example",
    )


def test_owner_observed_kalshi_escape_is_removed_from_curated_discovery():
    set_discovery_markets([
        _market("kalshi:full-game", "Full Game: over 183.5 points?", volume=20_800, trend=37, change=.045),
        _market("kalshi:washington", "Washington wins the game by over 21.5 points", volume=149, trend=13, change=.105),
        _market("kalshi:buxton-rbi", "Byron Buxton: 1+ RBIs?", volume=302, trend=11, change=-.02),
        _market("kalshi:buxton-bases", "Byron Buxton: 2+ total bases?", volume=289, trend=9, change=.005),
    ])

    response = _client().get("/api/v1/discovery?venue=kalshi&sort=trending&limit=100")
    assert response.status_code == 200
    assert response.headers["x-predibeacon-semantic-discovery"] == SEMANTIC_DISCOVERY_VERSION
    assert response.headers["x-predibeacon-monitored-candidate-count"] == "4"
    assert response.headers["x-predibeacon-curated-count"] == "1"
    payload = response.json()
    assert [item["title"] for item in payload] == ["Full Game: over 183.5 points?"]
    assert payload[0]["volume_usd"] >= MIN_DISCOVERY_VOLUME_USD
    assert payload[0]["relevance_score"] >= MIN_DISCOVERY_RELEVANCE_SCORE
    assert isinstance(payload[0]["attention_score"], (int, float))


def test_discovery_can_truthfully_be_empty_while_monitored_candidates_exist():
    set_discovery_markets([
        _market("kalshi:thin-a", "Thin A", volume=149, trend=100, change=.50),
        _market("kalshi:thin-b", "Thin B", volume=302, trend=90, change=.40),
    ])
    response = _client().get("/api/v1/discovery?venue=kalshi")
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["x-predibeacon-monitored-candidate-count"] == "2"
    assert response.headers["x-predibeacon-curated-count"] == "0"


def test_sorting_is_applied_before_semantic_subset_without_reintroducing_weak_markets():
    set_discovery_markets([
        _market("kalshi:weak-big-move", "Weak big move", volume=200, trend=100, change=.80),
        _market("kalshi:material-a", "Material A", volume=15_000, trend=40, change=.08),
        _market("kalshi:material-b", "Material B", volume=40_000, trend=35, change=.04),
    ])
    response = _client().get("/api/v1/discovery?venue=kalshi&sort=movers&limit=2")
    payload = response.json()
    assert len(payload) == 2
    assert "Weak big move" not in {item["title"] for item in payload}
    assert all(item["volume_usd"] >= MIN_DISCOVERY_VOLUME_USD for item in payload)


def test_semantic_fields_are_machine_verifiable_for_every_curated_item():
    set_discovery_markets([
        _market("kalshi:a", "A", volume=2_000, trend=50),
        _market("kalshi:b", "B", volume=100_000, trend=60),
    ])
    payload = _client().get("/api/v1/discovery?venue=kalshi&sort=volume").json()
    assert payload
    for item in payload:
        assert item["semantic_discovery_version"] == SEMANTIC_DISCOVERY_VERSION
        assert item["relevance_score"] >= MIN_DISCOVERY_RELEVANCE_SCORE
        assert 0 <= item["activity_confidence"] <= 1
        assert item["attention_reason_code"]
        assert 0 <= item["attention_score"] <= 100


def test_discovery_keeps_only_highest_ranked_contract_per_threshold_family():
    set_discovery_markets([
        _market(
            "polymarket:btc-100k",
            "Will the price of Bitcoin be above $100,000 on August 27?",
            volume=50_000,
            trend=70,
        ).model_copy(update={"venue": "polymarket"}),
        _market(
            "polymarket:btc-105k",
            "Will the price of Bitcoin be above $105,000 on August 27?",
            volume=40_000,
            trend=60,
        ).model_copy(update={"venue": "polymarket"}),
    ])

    payload = _client().get("/api/v1/discovery?sort=trending&limit=100").json()

    assert [item["canonical_id"] for item in payload] == ["polymarket:btc-100k"]
