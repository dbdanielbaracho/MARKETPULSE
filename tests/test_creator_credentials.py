import sqlite3

from fastapi.testclient import TestClient

from app.domain.revenue import AttributionRecord
from app.entrypoint import app
from app.storage.creator_credentials import CreatorCredentialStore
from app.storage.revenue import RevenueStore


client = TestClient(app)


def test_creator_token_is_hashed_at_rest_and_revocation_is_immediate(tmp_path):
    path = str(tmp_path / "creator-credentials.db")
    store = CreatorCredentialStore(path)
    raw_token = "pc_live_" + "x" * 48
    item = store.create(
        credential_id="credential-001",
        creator_id="creator-a",
        raw_token=raw_token,
    )
    assert store.authorize(raw_token).creator_id == "creator-a"

    with sqlite3.connect(path) as connection:
        token_hash = connection.execute(
            "SELECT token_hash FROM creator_credentials WHERE credential_id=?",
            (item.credential_id,),
        ).fetchone()[0]
    assert raw_token not in token_hash
    assert len(token_hash) == 64

    assert store.revoke(item.credential_id) is True
    try:
        store.authorize(raw_token)
    except PermissionError:
        pass
    else:
        raise AssertionError("revoked creator token remained authorized")


def test_creator_self_service_uses_token_identity_not_request_identity(tmp_path, monkeypatch):
    path = str(tmp_path / "creator-self-service.db")
    admin_token = "a" * 40
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", admin_token)

    revenue = RevenueStore(path)
    for suffix, creator_id in (("a", "creator-a"), ("b", "creator-b")):
        record = AttributionRecord(
            attribution_id=f"attr-{suffix}",
            click_id=f"click-{suffix}",
            partner_id="configured-partner",
            venue="kalshi",
            country="US",
        )
        revenue.record_click(record)
        revenue.record_click_context(
            click_id=record.click_id,
            market_id=f"market-{suffix}",
            creator_id=creator_id,
            channel="test",
        )

    issued = client.post(
        "/api/v1/admin/creator-credentials",
        json={"creator_id": "creator-a"},
        headers={"X-MarketPulse-Admin-Token": admin_token},
    )
    assert issued.status_code == 200
    payload = issued.json()
    creator_token = payload["creator_token"]
    assert creator_token.startswith("pc_live_")
    assert payload["creator_id"] == "creator-a"

    denied = client.get("/api/v1/creator/me/revenue")
    assert denied.status_code == 401

    response = client.get(
        "/api/v1/creator/me/revenue?creator_id=creator-b",
        headers={"X-PrediBeacon-Creator-Token": creator_token},
    )
    assert response.status_code == 200
    summary = response.json()
    assert summary["creator_id"] == "creator-a"
    assert summary["click_count"] == 1
    assert summary["market_count"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert "configured-partner" not in response.text
    assert "share_basis_points" not in response.text


def test_creator_credential_admin_routes_require_admin_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "creator-admin.db"))
    monkeypatch.setenv("MP_ADMIN_TOKEN", "a" * 40)
    response = client.post(
        "/api/v1/admin/creator-credentials",
        json={"creator_id": "creator-a"},
    )
    assert response.status_code == 401
