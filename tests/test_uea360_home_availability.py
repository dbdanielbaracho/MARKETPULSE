from datetime import datetime, timedelta, timezone

from app.middleware.home_client_dedup import _curate_market_payload


def _market(*, market_id: str, title: str, trend: float, volume: float) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "canonical_id": market_id,
        "title": title,
        "venue": "polymarket",
        "category": "Politics",
        "probability": 0.5,
        "probability_change": 0.0,
        "volume_usd": volume,
        "trend_score": trend,
        "observed_at": now.isoformat(),
        "closes_at": (now + timedelta(days=3)).isoformat(),
        "source_url": "https://polymarket.com/event/example",
    }


def test_valid_active_markets_do_not_all_disappear_only_because_trend_is_zero() -> None:
    """UEA360 regression: attention is ranking, not a validity/quality prerequisite.

    A quiet refresh can legitimately produce trend_score=0 for every contract.
    If the upstream contracts still have positive reported activity, valid metadata,
    and sufficient time to close, the homepage must retain quality-eligible markets
    instead of collapsing the default All view to zero.
    """
    items = [
        _market(market_id="poly:one", title="Will event one happen?", trend=0.0, volume=25_000.0),
        _market(market_id="poly:two", title="Will event two happen?", trend=0.0, volume=10_000.0),
    ]

    curated = _curate_market_payload(items)

    assert [item["canonical_id"] for item in curated] == ["poly:one", "poly:two"]


def test_zero_volume_stays_rejected_even_when_zero_trend_fallback_is_needed() -> None:
    items = [
        _market(market_id="poly:valid", title="Will valid event happen?", trend=0.0, volume=5_000.0),
        _market(market_id="poly:noise", title="Will noise event happen?", trend=0.0, volume=0.0),
    ]

    curated = _curate_market_payload(items)

    assert [item["canonical_id"] for item in curated] == ["poly:valid"]
