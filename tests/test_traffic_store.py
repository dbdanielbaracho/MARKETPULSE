from datetime import datetime, timezone

from app.storage.traffic import TrafficStore


def test_traffic_store_aggregates_without_visitor_identifiers(tmp_path):
    store = TrafficStore(str(tmp_path / "traffic.db"))
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    store.record_view(surface="home", channel="instagram", observed_at=now)
    store.record_view(surface="home", channel="instagram", observed_at=now)
    store.record_view(surface="market", market_id="market-one", channel="instagram", observed_at=now)

    data = store.summary(days=365)
    assert data["page_views"] == 3
    assert data["views_by_surface"] == {"home": 2, "market": 1}
    assert data["views_by_channel"] == {"instagram": 3}
    assert data["top_market_views"] == [{"market_id": "market-one", "views": 1}]
    assert "IP" in data["privacy"]


def test_traffic_store_sanitizes_dimension_values(tmp_path):
    store = TrafficStore(str(tmp_path / "traffic.db"))
    store.record_view(surface="market<script>", market_id="abc/../../secret", channel="social media!")
    data = store.summary(days=1)
    assert data["views_by_surface"] == {"marketscript": 1}
    assert data["views_by_channel"] == {"socialmedia": 1}
    assert data["top_market_views"][0]["market_id"] == "abc....secret"


def test_traffic_store_validates_summary_bounds(tmp_path):
    store = TrafficStore(str(tmp_path / "traffic.db"))
    for days in (0, 366):
        try:
            store.summary(days=days)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid days must be rejected")
