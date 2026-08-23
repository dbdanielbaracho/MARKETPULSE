from datetime import datetime, timedelta, timezone

from app import main as main_app
from app.main import DiscoveryMarket
from app.routes.public_closing_soon import closing_soon_markets


def _market(identifier: str, venue: str, closes_at):
    return DiscoveryMarket(
        canonical_id=identifier,
        title=identifier,
        venue=venue,
        probability=0.5,
        trend_score=50,
        observed_at=datetime.now(timezone.utc),
        closes_at=closes_at,
    )


def test_closing_soon_excludes_closed_and_unknown_and_orders_nearest_first(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        main_app,
        "_DISCOVERY",
        [
            _market("later", "kalshi", now + timedelta(days=5)),
            _market("soon", "polymarket", now + timedelta(hours=3)),
            _market("closed", "kalshi", now - timedelta(hours=1)),
            _market("unknown", "polymarket", None),
        ],
    )

    result = closing_soon_markets(limit=100)

    assert [item.canonical_id for item in result] == ["soon", "later"]


def test_closing_soon_applies_venue_filter(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        main_app,
        "_DISCOVERY",
        [
            _market("k", "kalshi", now + timedelta(hours=2)),
            _market("p", "polymarket", now + timedelta(hours=1)),
        ],
    )

    result = closing_soon_markets(venue="kalshi", limit=100)

    assert [item.canonical_id for item in result] == ["k"]


def test_closing_soon_reads_replaced_discovery_list(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(main_app, "_DISCOVERY", [_market("first", "kalshi", now + timedelta(days=1))])
    assert [item.canonical_id for item in closing_soon_markets(limit=100)] == ["first"]

    monkeypatch.setattr(main_app, "_DISCOVERY", [_market("replacement", "polymarket", now + timedelta(hours=1))])
    assert [item.canonical_id for item in closing_soon_markets(limit=100)] == ["replacement"]
