from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_alert_signals as alert_routes
from app.entrypoint import app
from app.services.intelligence import MarketSnapshot
from app.storage.snapshots import SnapshotStore


client = TestClient(app)


def _seed(tmp_path, monkeypatch) -> tuple[str, datetime]:
    database = tmp_path / "alerts.db"
    monkeypatch.setenv("MP_DATABASE_PATH", str(database))
    now = datetime.now(timezone.utc)
    market_id = "kalshi:KXALERT"
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id=market_id,
            title="Will X happen?",
            venue="kalshi",
            probability=.61,
            probability_change=.06,
            trend_score=80,
            observed_at=now,
            closes_at=now + timedelta(hours=23),
            source_url="https://kalshi.com/markets/KXALERT",
        )
    ])
    store = SnapshotStore(database)
    store.append(MarketSnapshot(market_id, .50, 10_000, now - timedelta(hours=2)))
    store.append(MarketSnapshot(market_id, .61, 20_000, now))
    return market_id, now


def test_alert_snapshot_aggregates_only_observable_signals(tmp_path, monkeypatch):
    market_id, now = _seed(tmp_path, monkeypatch)

    async def fake_execution(_):
        return SimpleNamespace(available=True, score=40, grade="weak", spread_points=8.0)

    async def fake_activity(_):
        return SimpleNamespace(
            sample_size=20,
            signal_count=1,
            signals=[SimpleNamespace(notional_usd=12_500.0, occurred_at=now)],
        )

    async def fake_cross(_):
        return SimpleNamespace(
            counterpart=SimpleNamespace(canonical_id="polymarket:42"),
            verification=SimpleNamespace(equivalent_contracts=True, confidence=92, gap_points=6.5),
        )

    monkeypatch.setattr(alert_routes, "_safe_execution", fake_execution)
    monkeypatch.setattr(alert_routes, "_safe_trade_activity", fake_activity)
    monkeypatch.setattr(alert_routes, "_safe_cross_platform", fake_cross)

    response = client.get("/api/v1/market/alert-signals", params={"market_id": market_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["probability"] == .61
    assert payload["breaking"]["available"] is True
    assert payload["breaking"]["active"] is True
    assert payload["execution"] == {"available": True, "score": 40, "grade": "weak", "spread_points": 8.0}
    assert payload["large_trade_activity"]["signal_count"] == 1
    assert payload["large_trade_activity"]["largest_notional_usd"] == 12500
    assert payload["large_trade_activity"]["latest_signal_key"] is not None
    assert payload["cross_platform"]["equivalent_contracts"] is True
    assert payload["cross_platform"]["gap_points"] == 6.5
    assert payload["cross_platform"]["counterpart_id"] == "polymarket:42"
    assert payload["closing"]["available"] is True
    assert 22 <= payload["closing"]["remaining_hours"] <= 23
    assert payload["closing"]["closes_at"] is not None
    assert payload["evidence"]["available"] is True
    assert payload["evidence"]["item_count"] >= 1
    assert payload["evidence"]["latest_evidence_key"].startswith("ev_")
    assert payload["evidence"]["latest_evidence_at"] is not None
    assert "Missing data never triggers a signal" in payload["disclaimer"]
    assert response.headers["cache-control"] == "private, max-age=10"


def test_alert_snapshot_fails_closed_when_optional_live_layers_are_unavailable(tmp_path, monkeypatch):
    market_id, _ = _seed(tmp_path, monkeypatch)

    async def unavailable(_):
        return None

    monkeypatch.setattr(alert_routes, "_safe_execution", unavailable)
    monkeypatch.setattr(alert_routes, "_safe_trade_activity", unavailable)
    monkeypatch.setattr(alert_routes, "_safe_cross_platform", unavailable)

    response = client.get("/api/v1/market/alert-signals", params={"market_id": market_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution"]["available"] is False
    assert payload["large_trade_activity"]["available"] is False
    assert payload["large_trade_activity"]["signal_count"] == 0
    assert payload["cross_platform"]["available"] is False
    assert payload["cross_platform"]["equivalent_contracts"] is False
    assert payload["closing"]["available"] is True
    assert payload["evidence"]["available"] is True


def test_alert_snapshot_fails_closed_without_closing_or_evidence(tmp_path, monkeypatch):
    database = tmp_path / "alerts-empty.db"
    monkeypatch.setenv("MP_DATABASE_PATH", str(database))
    now = datetime.now(timezone.utc)
    market_id = "polymarket:no-context"
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id=market_id,
            title="Context unavailable?",
            venue="polymarket",
            probability=.5,
            trend_score=50,
            observed_at=now,
        )
    ])

    async def unavailable(_):
        return None

    monkeypatch.setattr(alert_routes, "_safe_execution", unavailable)
    monkeypatch.setattr(alert_routes, "_safe_trade_activity", unavailable)
    monkeypatch.setattr(alert_routes, "_safe_cross_platform", unavailable)
    response = client.get("/api/v1/market/alert-signals", params={"market_id": market_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["closing"] == {"available": False, "closes_at": None, "remaining_hours": None}
    assert payload["evidence"] == {
        "available": False,
        "item_count": 0,
        "latest_evidence_key": None,
        "latest_evidence_at": None,
    }


def test_alert_signal_endpoint_is_registered():
    assert "/api/v1/market/alert-signals" in app.openapi()["paths"]
