from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.storage.api_accounts import ApiCustomerStore, ApiSubscriptionEntitlement


client = TestClient(app)


def _configure(monkeypatch, tmp_path):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("MP_ADMIN_TOKEN", "a" * 40)
    monkeypatch.setenv("MP_API_PRO_PRODUCT_ID", "prod_api_pro")
    monkeypatch.setenv("MP_STRIPE_API_PRO_PRICE_ID", "price_api_pro")
    monkeypatch.setenv("MP_API_PRO_DAILY_LIMIT", "200")
    monkeypatch.setenv("MP_API_PRO_SCOPES", "markets:read,history:read")


def test_subscriber_key_issuance_requires_live_entitlement_and_never_lists_secret(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    created = client.post(
        "/api/v1/admin/api-accounts",
        headers={"X-MarketPulse-Admin-Token": "a" * 40},
        json={"email": "customer@example.com"},
    )
    assert created.status_code == 200
    body = created.json()
    account_id = body["account_id"]
    token = body["account_token"]
    assert token.startswith("pb_apiacct_")
    assert created.headers["cache-control"] == "no-store"

    headers = {"X-PrediBeacon-API-Account-Token": token}
    me = client.get("/api/v1/api-account/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["api_access_active"] is False
    denied = client.post("/api/v1/api-account/keys", headers=headers, json={"name": "primary"})
    assert denied.status_code == 403

    store = ApiCustomerStore(str(tmp_path / "app.db"))
    store.upsert_entitlement(
        ApiSubscriptionEntitlement(
            account_id=account_id,
            plan="pro",
            product_id="prod_api_pro",
            subscription_id="sub_test_123",
            status="active",
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    issued = client.post("/api/v1/api-account/keys", headers=headers, json={"name": "primary"})
    assert issued.status_code == 200
    key_body = issued.json()
    raw_key = key_body["api_key"]
    assert key_body["plan"] == "pro"
    assert key_body["daily_limit"] == 200
    assert set(key_body["scopes"]) == {"markets:read", "history:read"}
    assert "prod_api_pro" not in issued.text
    assert "price_api_pro" not in issued.text

    listed = client.get("/api/v1/api-account/keys", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["key_id"] == key_body["key_id"]
    assert raw_key not in listed.text

    api = client.get("/api/v1/commercial/markets", headers={"X-PrediBeacon-API-Key": raw_key})
    assert api.status_code == 200

    store.upsert_entitlement(
        ApiSubscriptionEntitlement(
            account_id=account_id,
            plan="pro",
            product_id="prod_api_pro",
            subscription_id="sub_test_123",
            status="canceled",
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    blocked = client.get("/api/v1/commercial/markets", headers={"X-PrediBeacon-API-Key": raw_key})
    assert blocked.status_code == 401
    assert "subscription is not active" in blocked.text


def test_account_can_revoke_only_its_own_key(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    responses = []
    for email in ("one@example.com", "two@example.com"):
        response = client.post(
            "/api/v1/admin/api-accounts",
            headers={"X-MarketPulse-Admin-Token": "a" * 40},
            json={"email": email},
        )
        assert response.status_code == 200
        responses.append(response.json())
    store = ApiCustomerStore(str(tmp_path / "app.db"))
    for item in responses:
        store.upsert_entitlement(
            ApiSubscriptionEntitlement(item["account_id"], "pro", "prod_api_pro", "sub_" + item["account_id"][-8:], "active", None)
        )
    first_headers = {"X-PrediBeacon-API-Account-Token": responses[0]["account_token"]}
    second_headers = {"X-PrediBeacon-API-Account-Token": responses[1]["account_token"]}
    issued = client.post("/api/v1/api-account/keys", headers=first_headers, json={"name": "owned"}).json()
    other = client.delete(f"/api/v1/api-account/keys/{issued['key_id']}", headers=second_headers)
    assert other.status_code == 404
    own = client.delete(f"/api/v1/api-account/keys/{issued['key_id']}", headers=first_headers)
    assert own.status_code == 200
