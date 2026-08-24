from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.main as core
from app.entrypoint import app


client = TestClient(app)


def _market(identifier: str, *, venue: str, score: float, closes_at: datetime):
    now = datetime.now(timezone.utc)
    return core.DiscoveryMarket(
        canonical_id=f"{venue}:{identifier}",
        title=f"Market {identifier}",
        venue=venue,
        probability=0.5,
        probability_change=score / 1000,
        volume_usd=1000,
        trend_score=score,
        observed_at=now,
        closes_at=closes_at,
        source_url=f"https://{'kalshi.com' if venue == 'kalshi' else 'polymarket.com'}/markets/{identifier}",
    )


def test_relevant_discovery_excludes_closed_contracts_and_preserves_score_order():
    now = datetime.now(timezone.utc)
    original = list(core._DISCOVERY)
    try:
        core.set_discovery_markets([
            _market("high", venue="kalshi", score=90, closes_at=now + timedelta(days=5)),
            _market("closed", venue="polymarket", score=100, closes_at=now - timedelta(hours=1)),
            _market("medium", venue="kalshi", score=60, closes_at=now + timedelta(days=5)),
            _market("lower-other-venue", venue="polymarket", score=30, closes_at=now + timedelta(days=5)),
            _market("low", venue="kalshi", score=10, closes_at=now + timedelta(days=5)),
        ])
        response = client.get("/api/v1/markets/relevant?limit=100")
        assert response.status_code == 200
        body = response.json()
        ids = [item["canonical_id"] for item in body]
        assert "polymarket:closed" not in ids
        scores = [item["relevance_score"] for item in body]
        assert scores == sorted(scores, reverse=True)
    finally:
        core.set_discovery_markets(original)
