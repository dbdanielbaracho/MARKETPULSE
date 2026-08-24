from fastapi.testclient import TestClient

from app.domain.revenue import AttributionRecord, RevenueState
from app.entrypoint import app
from app.storage.revenue import RevenueStore


client = TestClient(app)


def test_creator_paid_revenue_flow_is_agreement_driven_authenticated_and_revocable(tmp_path, monkeypatch):
    path = str(tmp_path / "creator-e2e.db")
    admin_token = "admin-e2e-" + "x" * 40
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", admin_token)
    admin_headers = {"X-MarketPulse-Admin-Token": admin_token}

    revenue = RevenueStore(path)
    record = AttributionRecord(
        attribution_id="creator-e2e-attribution",
        click_id="creator-e2e-click",
        partner_id="synthetic-partner-fixture",
        venue="kalshi",
        country="US",
    )
    revenue.record_click(record)
    revenue.record_click_context(
        click_id=record.click_id,
        market_id="kalshi:creator-e2e-market",
        campaign_id="creator-e2e-campaign",
        creator_id="creator-e2e",
        channel="test",
    )
    for state, event_id in (
        (RevenueState.ATTRIBUTED, "creator-e2e-event-1"),
        (RevenueState.QUALIFIED, "creator-e2e-event-2"),
        (RevenueState.COMMISSION_PENDING, "creator-e2e-event-3"),
    ):
        revenue.transition(record.attribution_id, state, partner_event_id=event_id)
    revenue.transition(
        record.attribution_id,
        RevenueState.APPROVED,
        commission_amount=12.50,
        currency="USD",
        partner_event_id="creator-e2e-event-4",
    )
    revenue.transition(record.attribution_id, RevenueState.PAYABLE, partner_event_id="creator-e2e-event-5")
    revenue.transition(record.attribution_id, RevenueState.PAID, partner_event_id="creator-e2e-event-6")

    configured = client.post(
        "/api/v1/admin/creators/creator-e2e/agreement",
        headers=admin_headers,
        json={"agreement_id": "creator-e2e-agreement", "share_basis_points": 4000},
    )
    assert configured.status_code == 200
    assert configured.json()["approved"] is False
    assert "share_basis_points" not in configured.text

    issued = client.post(
        "/api/v1/admin/creator-credentials",
        headers=admin_headers,
        json={"creator_id": "creator-e2e"},
    )
    assert issued.status_code == 200
    creator_token = issued.json()["creator_token"]
    creator_headers = {"X-PrediBeacon-Creator-Token": creator_token}

    pending = client.get("/api/v1/creator/me/revenue", headers=creator_headers)
    assert pending.status_code == 200
    assert pending.json()["creator_amount_due"] is None

    approved = client.post(
        "/api/v1/admin/creators/creator-e2e/agreement/approve",
        headers=admin_headers,
        json={"agreement_id": "creator-e2e-agreement"},
    )
    assert approved.status_code == 200
    assert approved.json()["approved"] is True
    assert "share_basis_points" not in approved.text

    creator_view = client.get("/api/v1/creator/me/revenue", headers=creator_headers)
    assert creator_view.status_code == 200
    body = creator_view.json()
    assert body["creator_id"] == "creator-e2e"
    assert body["paid_partner_revenue_totals"] == {"USD": 12.5}
    assert body["creator_amount_due"] == {"USD": 5.0}
    assert creator_view.headers["cache-control"] == "no-store"
    for forbidden in (
        "synthetic-partner-fixture",
        "creator-e2e-agreement",
        "share_basis_points",
        "4000",
    ):
        assert forbidden not in creator_view.text

    revoked = client.post(
        "/api/v1/admin/creators/creator-e2e/agreement/revoke",
        headers=admin_headers,
    )
    assert revoked.status_code == 200

    after_revoke = client.get("/api/v1/creator/me/revenue", headers=creator_headers)
    assert after_revoke.status_code == 200
    assert after_revoke.json()["creator_amount_due"] is None
