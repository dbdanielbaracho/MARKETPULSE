import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.domain.revenue import AttributionRecord, RevenueState
from app.main import app
from app.storage.revenue import RevenueStore
from app.services.outbound import PartnerRoute, resolve_outbound


def test_outbound_fails_closed_without_verified_route():
    decision = resolve_outbound(
        venue="kalshi",
        country="US",
        routes=[PartnerRoute("k", "kalshi", "US", "https://kalshi.com/markets/x", enabled=True)],
    )
    assert decision.allowed is False
    assert decision.reason == "no_verified_route"


def test_outbound_rejects_untrusted_host_even_when_enabled():
    decision = resolve_outbound(
        venue="kalshi",
        country="US",
        routes=[PartnerRoute("k", "kalshi", "US", "https://evil.example/phish", enabled=True, commercial_verified=True, allowed_hosts=("kalshi.com",))],
    )
    assert decision.allowed is False


def test_outbound_accepts_server_side_https_allowlist():
    decision = resolve_outbound(
        venue="kalshi",
        country="US",
        routes=[PartnerRoute("k", "kalshi", "US", "https://kalshi.com/markets/x", enabled=True, commercial_verified=True, allowed_hosts=("kalshi.com",))],
    )
    assert decision.allowed is True
    assert decision.partner_id == "k"


def test_revenue_happy_path_and_amount_requires_currency():
    record = AttributionRecord("a1", "c1", "p1", "kalshi", "US")
    record = record.transition(RevenueState.ATTRIBUTED)
    record = record.transition(RevenueState.QUALIFIED)
    record = record.transition(RevenueState.COMMISSION_PENDING)
    with pytest.raises(ValueError):
        record.transition(RevenueState.APPROVED, commission_amount=12.50)
    record = record.transition(RevenueState.APPROVED, commission_amount=12.50, currency="usd")
    record = record.transition(RevenueState.PAYABLE)
    record = record.transition(RevenueState.PAID)
    assert record.state is RevenueState.PAID
    assert record.commission_amount == 12.50
    assert record.currency == "USD"


def test_invalid_revenue_transition_fails_closed():
    record = AttributionRecord("a1", "c1", "p1", "kalshi", "US")
    with pytest.raises(ValueError):
        record.transition(RevenueState.PAID)


def test_duplicate_state_is_idempotent():
    record = AttributionRecord("a1", "c1", "p1", "kalshi", "US")
    assert record.transition(RevenueState.CLICKED) is record


def _signed_partner_post(client, venue, secret, payload, timestamp=None):
    timestamp = timestamp or int(time.time())
    body = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + body.encode(), hashlib.sha256).hexdigest()
    return client.post(
        f"/api/v1/partners/{venue}/events",
        content=body,
        headers={
            "content-type": "application/json",
            "X-PrediBeacon-Partner-Timestamp": str(timestamp),
            "X-PrediBeacon-Partner-Signature": f"sha256={signature}",
        },
    )


def test_signed_partner_reconciliation_and_creator_paid_summary(tmp_path, monkeypatch):
    path = str(tmp_path / "revenue.db")
    secret = "partner-secret-" + "x" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_KALSHI_WEBHOOK_SECRET", secret)
    store = RevenueStore(path)
    store.record_click(AttributionRecord("attr-1", "click-1", "kalshi-partner", "kalshi", "US"))
    store.record_click_context(click_id="click-1", market_id="kalshi:m", campaign_id="creator-campaign", creator_id="creator-1", channel="tiktok", referrer=None)
    client = TestClient(app)
    states = ["attributed", "qualified", "commission_pending", "approved", "payable", "paid"]
    last = None
    for index, state in enumerate(states):
        payload = {"event_id": f"event-{index}", "click_id": "click-1", "state": state}
        if state == "approved":
            payload.update({"commission_amount": 12.50, "currency": "USD"})
        last = _signed_partner_post(client, "kalshi", secret, payload)
        assert last.status_code == 200, last.text
    assert last.json()["state"] == "paid"
    assert last.json()["commission_amount"] == 12.50
    summary = store.creator_summary("creator-1")
    assert summary["paid_partner_revenue_totals"] == {"USD": 12.50}
    assert summary["creator_amount_due"] is None


def test_partner_events_reject_bad_signature_stale_time_and_wrong_venue(tmp_path, monkeypatch):
    path = str(tmp_path / "revenue.db")
    secret = "partner-secret-" + "y" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_KALSHI_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("MP_POLYMARKET_WEBHOOK_SECRET", secret)
    store = RevenueStore(path)
    store.record_click(AttributionRecord("attr-2", "click-2", "kalshi-partner", "kalshi", "US"))
    client = TestClient(app)
    payload = {"event_id": "bad-event", "click_id": "click-2", "state": "attributed"}
    bad = client.post("/api/v1/partners/kalshi/events", json=payload, headers={"X-PrediBeacon-Partner-Timestamp": str(int(time.time())), "X-PrediBeacon-Partner-Signature": "bad"})
    stale = _signed_partner_post(client, "kalshi", secret, payload, int(time.time()) - 600)
    wrong = _signed_partner_post(client, "polymarket", secret, payload)
    assert bad.status_code == 401
    assert stale.status_code == 401
    assert wrong.status_code == 409
    assert store.get("attr-2").state is RevenueState.CLICKED
