from fastapi.testclient import TestClient

from app.domain.revenue import AttributionRecord, RevenueState
from app.entrypoint import app
from app.storage.creator_agreements import CreatorAgreementStore
from app.storage.creator_credentials import CreatorCredentialStore
from app.storage.revenue import RevenueStore


def _paid_revenue(path: str, creator_id: str, amount: float = 12.50) -> None:
    store = RevenueStore(path)
    store.record_click(AttributionRecord("self-attr", "self-click", "partner", "kalshi", "US"))
    store.record_click_context(
        click_id="self-click",
        market_id="kalshi:self-market",
        campaign_id="self-campaign",
        creator_id=creator_id,
        channel="test",
    )
    store.transition("self-attr", RevenueState.ATTRIBUTED, partner_event_id="self-event-1")
    store.transition("self-attr", RevenueState.QUALIFIED, partner_event_id="self-event-2")
    store.transition("self-attr", RevenueState.COMMISSION_PENDING, partner_event_id="self-event-3")
    store.transition(
        "self-attr",
        RevenueState.APPROVED,
        commission_amount=amount,
        currency="USD",
        partner_event_id="self-event-4",
    )
    store.transition("self-attr", RevenueState.PAYABLE, partner_event_id="self-event-5")
    store.transition("self-attr", RevenueState.PAID, partner_event_id="self-event-6")


def _credential(path: str, creator_id: str) -> str:
    raw = "pc_live_" + "s" * 48
    CreatorCredentialStore(path).create(
        credential_id="credential-self-001",
        creator_id=creator_id,
        raw_token=raw,
    )
    return raw


def test_authenticated_creator_sees_agreement_driven_amount_without_private_terms(tmp_path, monkeypatch):
    path = str(tmp_path / "creator-self.db")
    creator_id = "creator-self"
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    _paid_revenue(path, creator_id)
    agreements = CreatorAgreementStore(path)
    agreements.configure(
        creator_id=creator_id,
        agreement_id="agreement-self-001",
        share_basis_points=4000,
        approved=False,
    )
    agreements.approve(creator_id, "agreement-self-001")
    token = _credential(path, creator_id)

    response = TestClient(app).get(
        "/api/v1/creator/me/revenue",
        headers={"X-PrediBeacon-Creator-Token": token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["creator_id"] == creator_id
    assert body["paid_partner_revenue_totals"] == {"USD": 12.50}
    assert body["creator_amount_due"] == {"USD": 5.0}
    assert body["agreement_status"] == "approved"
    assert response.headers["cache-control"] == "no-store"
    assert "share_basis_points" not in response.text
    assert "agreement-self-001" not in response.text


def test_authenticated_creator_amount_fails_closed_without_approved_agreement(tmp_path, monkeypatch):
    path = str(tmp_path / "creator-self.db")
    creator_id = "creator-self"
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    _paid_revenue(path, creator_id)
    CreatorAgreementStore(path).configure(
        creator_id=creator_id,
        agreement_id="agreement-self-001",
        share_basis_points=4000,
        approved=False,
    )
    token = _credential(path, creator_id)

    response = TestClient(app).get(
        "/api/v1/creator/me/revenue",
        headers={"X-PrediBeacon-Creator-Token": token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["paid_partner_revenue_totals"] == {"USD": 12.50}
    assert body["creator_amount_due"] is None
    assert body["agreement_status"] == "not_approved"
    assert "share_basis_points" not in response.text
    assert "agreement-self-001" not in response.text
