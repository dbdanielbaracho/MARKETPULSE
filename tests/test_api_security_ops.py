import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.api_keys import ApiKeyStore


client = TestClient(app)


def test_api_key_rotation_is_atomic_and_auditable(tmp_path):
    store = ApiKeyStore(str(tmp_path / "keys.db"))
    old_token = "pb_live_" + "a" * 40
    new_token = "pb_live_" + "b" * 40
    store.create(
        key_id="old",
        raw_token=old_token,
        name="Production client",
        plan="pro",
        scopes=("markets:read", "history:read"),
        daily_limit=500,
    )

    replacement = store.rotate(old_key_id="old", new_key_id="new", raw_token=new_token)

    assert replacement.key_id == "new"
    assert replacement.active is True
    assert replacement.plan == "pro"
    assert replacement.scopes == ("history:read", "markets:read")
    with pytest.raises(PermissionError):
        store.authorize(old_token, "markets:read")
    assert store.authorize(new_token, "markets:read").key_id == "new"

    records = {item.key_id: item for item in store.list_keys()}
    assert records["old"].active is False
    assert records["old"].revoked_at is not None
    assert records["new"].active is True


def test_api_key_revocation_is_idempotently_fail_closed(tmp_path):
    store = ApiKeyStore(str(tmp_path / "keys.db"))
    token = "pb_live_" + "c" * 40
    store.create(
        key_id="key",
        raw_token=token,
        name="Client",
        plan="starter",
        scopes=("markets:read",),
        daily_limit=10,
    )
    assert store.revoke("key") is True
    assert store.revoke("key") is False
    with pytest.raises(PermissionError):
        store.authorize(token, "markets:read")


def test_request_ids_timing_and_declared_body_limit():
    response = client.get("/health", headers={"X-Request-ID": "release-test-123"})
    assert response.headers["x-request-id"] == "release-test-123"
    assert response.headers["server-timing"].startswith("app;dur=")

    generated = client.get("/health", headers={"X-Request-ID": "bad value"})
    assert generated.headers["x-request-id"] != "bad value"

    rejected = client.post(
        "/api/v1/admin/api-keys",
        content=b"{}",
        headers={"Content-Length": "1048577"},
    )
    assert rejected.status_code == 413
    assert rejected.headers["cache-control"] == "no-store"
    assert rejected.json()["request_id"] == rejected.headers["x-request-id"]
