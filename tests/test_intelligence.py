from datetime import datetime, timedelta, timezone

from app.services.intelligence import MarketSnapshot, attention_score, probability_change, signal, trend_score
from app.storage.snapshots import SnapshotStore


def make_snapshot(probability: float, volume: float, minute: int = 0, volume_24h: float | None = None) -> MarketSnapshot:
    return MarketSnapshot(
        "kalshi:TEST",
        probability,
        volume,
        datetime(2026, 8, 21, 20, minute, tzinfo=timezone.utc),
        volume_24h,
    )


def test_probability_change_is_percentage_point_delta():
    assert probability_change(make_snapshot(0.67, 1000, 1), make_snapshot(0.54, 1000, 0)) == 0.13


def test_first_observation_has_no_fake_change():
    current = make_snapshot(0.67, 1000)
    assert probability_change(current, None) is None
    assert signal(current).probability_change is None


def test_trend_score_is_bounded():
    current = make_snapshot(1.0, 999999)
    previous = make_snapshot(0.0, 0)
    assert trend_score(current, previous) == 100.0


def test_trend_score_discounts_same_move_when_activity_is_thin():
    previous = make_snapshot(0.50, 100000, 0)
    thin = make_snapshot(0.62, 275, 1)
    active = make_snapshot(0.62, 100000, 1)
    assert trend_score(thin, previous) < trend_score(active, previous)
    assert trend_score(thin, previous) < 30


def test_lifetime_volume_cannot_fake_current_activity_when_24h_is_reported():
    previous = make_snapshot(0.50, 10_000_000, 0, volume_24h=0)
    dormant = make_snapshot(0.62, 10_000_000, 1, volume_24h=0)
    active = make_snapshot(0.62, 10_000_000, 1, volume_24h=100_000)
    assert trend_score(dormant, previous) == 0
    assert trend_score(active, previous) > trend_score(dormant, previous)
    assert signal(dormant, previous).volume_usd == 0
    assert signal(active, previous).volume_usd == 100_000


def test_missing_24h_field_falls_back_to_lifetime_for_legacy_provider_fixture():
    previous = make_snapshot(0.50, 100_000, 0)
    current = make_snapshot(0.62, 100_000, 1)
    assert trend_score(current, previous) > 0
    assert signal(current, previous).volume_usd == 100_000


def test_attention_score_uses_same_activity_confidence_as_trend():
    thin = attention_score(
        trend_score_value=20,
        probability_change_value=-0.12,
        volume_usd=275,
        hours_to_close=48,
    )
    active = attention_score(
        trend_score_value=20,
        probability_change_value=-0.12,
        volume_usd=100000,
        hours_to_close=48,
    )
    assert thin < active


def test_snapshot_store_returns_previous(tmp_path):
    store = SnapshotStore(tmp_path / "marketpulse.db")
    first = make_snapshot(0.54, 1000, 0)
    second = make_snapshot(0.67, 2000, 1)
    store.append(first)
    store.append(second)
    previous = store.previous(second.canonical_id, second.observed_at.isoformat())
    assert previous is not None
    assert previous.probability == 0.54


def test_snapshot_insert_is_idempotent(tmp_path):
    store = SnapshotStore(tmp_path / "marketpulse.db")
    item = make_snapshot(0.50, 1000)
    store.append(item)
    store.append(item)
    previous = store.previous(item.canonical_id, (item.observed_at + timedelta(seconds=1)).isoformat())
    assert previous is not None
