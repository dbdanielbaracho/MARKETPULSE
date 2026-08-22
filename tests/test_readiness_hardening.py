from datetime import datetime, timezone

from app.main import (
    DiscoveryMarket,
    app,
    health,
    related_markets,
    set_discovery_markets,
)


def _market(identifier: str, title: str, category: str, venue: str):
    return DiscoveryMarket(
        canonical_id=identifier,
        title=title,
        venue=venue,
        category=category,
        probability=0.5,
        trend_score=70,
        observed_at=datetime.now(timezone.utc),
    )


def test_public_runtime_identity_is_predibeacon():
    assert app.title == "PrediBeacon"
    assert health()["service"] == "predibeacon-web"


def test_related_markets_never_claim_contract_equivalence():
    set_discovery_markets([
        _market("a", "Will US inflation fall below 3 percent in 2027?", "economy", "kalshi"),
        _market("b", "Will US inflation fall below 2 percent in 2027?", "economy", "polymarket"),
        _market("c", "Will a spacecraft land on Mars in 2027?", "science", "kalshi"),
    ])
    try:
        results = related_markets("a")
        assert results
        assert all(item.equivalent_contracts is False for item in results)
        assert all(item.relationship in {"related", "insufficient_evidence"} for item in results)
        assert any("category" in reason.lower() for reason in results[0].reasons)
    finally:
        set_discovery_markets([])
