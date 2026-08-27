from datetime import datetime, timedelta, timezone

from app.services.discovery_semantics import curate_semantic_discovery, discovery_family_key


def _market(market_id: str, title: str, *, volume: float) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "canonical_id": market_id,
        "title": title,
        "venue": "polymarket",
        "volume_usd": volume,
        "trend_score": 50.0,
        "probability": 0.55,
        "probability_change": 0.03,
        "observed_at": now.isoformat(),
        "closes_at": (now + timedelta(days=2)).isoformat(),
        "source_url": "https://polymarket.com/",
    }


def test_threshold_variants_share_one_family() -> None:
    first = "Will the price of Bitcoin be above $120,000 on August 27?"
    second = "Will the price of Bitcoin be above $125,000 on August 27?"
    assert discovery_family_key(first) == discovery_family_key(second)


def test_semantic_discovery_keeps_only_first_ranked_market_per_family() -> None:
    items = [
        _market("poly-best", "Will the price of Bitcoin be above $120,000 on August 27?", volume=250_000),
        _market("poly-duplicate", "Will the price of Bitcoin be above $125,000 on August 27?", volume=200_000),
        _market("poly-other", "Will Ethereum be above $5,000 on August 27?", volume=180_000),
    ]

    curated = curate_semantic_discovery(items)
    ids = [item["canonical_id"] for item in curated]

    assert "poly-best" in ids
    assert "poly-duplicate" not in ids
    assert "poly-other" in ids
    assert len(ids) == 2
