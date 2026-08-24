from fastapi.testclient import TestClient

from app.domain.revenue import AttributionRecord, RevenueState
from app.entrypoint import app
from app.storage.revenue import RevenueStore


def _paid_creator_revenue(path: str, *, creator_id: str, amount: float = 12.50) -> None:
    store = RevenueStore(path)
    store.record_click(AttributionRecord("creator-attr-1", "creator-click-1", "partner", "kalshi", "US"))
    store.record_click_context(
        click_id="creator-click-1",
        market_id="kalshi:creator-market",
        campaign_id="creator-campaign",
        creator_id=creator_id,
        channel="tiktok",
    )
    store.transition("creator-attr-1", RevenueState.ATTRIBUTED, partner_event_id="creator-event-1")
    store.transition("creator-attr-1", RevenueState.QUALIFIED, partner_event_id="creator-event-2")
    store.transition("creator-attr-1", RevenueState.COMMISSION_PENDING, partner_event_id="creator-event-3")
    store.transition(
        "creator-attr-1",
        RevenueState.APPROVED,
        commission_amount=amount,
        currency="USD",
        partner_event_id="creator-event-4",
    )
    store.transition("creator-attr-1", RevenueState.PAYABLE, partner_event_id="creator-event-5")
    store.transition("creator-attr-1", RevenueState.PAID, partner_event_id="creator-event-6")


def _headers(token: str) -> dict[str, str]:
    return {"X-MarketPulse-Admin-Token": token}


def _configure(client: TestClient, token: str, creator_id: str, agreement_id: str, share: int):
    return client.post(
        f"/api/v1/admin/creators/{creator_id}/revenue-share-agreement",
        headers=_headers(token),
        json={"agreement_id": agreement_id, "share_basis_points": share},
    )


def _approve(client: TestClient, token: str, creator_id: str, agreement_id: str):
    return client.post(
        f"/api/v1/admin/creators/{creator_id}/revenue-share-agreement/approve",
        headers=_headers(token),
        json={"agreement_id": agreement_id},
    )


def test_creator_share_fails_closed_without_approved_agreement(tmp_path, monkeypatch):
    path = str(tmp_path / "creator.db")
    token = "admin-token-" + "x" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    _paid_creator_revenue(path, creator_id="creator-1")

    response = TestClient(app).get(
        "/api/v1/admin/creators/creator-1/revenue-share",
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["paid_partner_revenue_totals"] == {"USD": 12.50}
    assert body["agreement"] is None
    assert body["creator_amount_due"] is None


def test_unapproved_configuration_remains_unusable(tmp_path, monkeypatch):
    path = str(tmp_path / "creator.db")
    token = "admin-token-" + "u" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    _paid_creator_revenue(path, creator_id="creator-2")
    client = TestClient(app)

    configured = _configure(client, token, "creator-2", "agreement-creator-2-v1", 4000)
    assert configured.status_code == 200, configured.text
    assert configured.json()["approved"] is False

    snapshot = client.get(
        "/api/v1/admin/creators/creator-2/revenue-share",
        headers=_headers(token),
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["agreement"] is None
    assert snapshot.json()["creator_amount_due"] is None


def test_creator_share_uses_only_paid_partner_revenue_after_exact_approval(tmp_path, monkeypatch):
    path = str(tmp_path / "creator.db")
    token = "admin-token-" + "y" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    _paid_creator_revenue(path, creator_id="creator-3")
    client = TestClient(app)

    configured = _configure(client, token, "creator-3", "agreement-creator-3-v1", 4000)
    assert configured.status_code == 200
    approved = _approve(client, token, "creator-3", "agreement-creator-3-v1")
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved"] is True

    response = client.get(
        "/api/v1/admin/creators/creator-3/revenue-share",
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["paid_partner_revenue_totals"] == {"USD": 12.50}
    assert body["agreement"]["agreement_id"] == "agreement-creator-3-v1"
    assert body["agreement"]["approved"] is True
    assert body["creator_amount_due"] == {"USD": 5.0}


def test_approval_rejects_wrong_or_missing_agreement(tmp_path, monkeypatch):
    path = str(tmp_path / "creator.db")
    token = "admin-token-" + "a" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    client = TestClient(app)

    configured = _configure(client, token, "creator-a", "agreement-creator-a-v1", 1000)
    assert configured.status_code == 200
    wrong = _approve(client, token, "creator-a", "agreement-creator-a-v2")
    assert wrong.status_code == 400
    missing = _approve(client, token, "creator-b", "agreement-creator-a-v1")
    assert missing.status_code == 404


def test_revocation_immediately_disables_creator_amount(tmp_path, monkeypatch):
    path = str(tmp_path / "creator.db")
    token = "admin-token-" + "z" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    _paid_creator_revenue(path, creator_id="creator-4")
    client = TestClient(app)
    assert _configure(client, token, "creator-4", "agreement-creator-4-v1", 2500).status_code == 200
    assert _approve(client, token, "creator-4", "agreement-creator-4-v1").status_code == 200

    revoked = client.post(
        "/api/v1/admin/creators/creator-4/revenue-share-agreement/revoke",
        headers=_headers(token),
    )
    assert revoked.status_code == 200
    assert revoked.json()["approved"] is False

    snapshot = client.get(
        "/api/v1/admin/creators/creator-4/revenue-share",
        headers=_headers(token),
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["agreement"] is None
    assert snapshot.json()["creator_amount_due"] is None


def test_creator_share_route_rejects_unbounded_or_ambiguous_configuration(tmp_path, monkeypatch):
    path = str(tmp_path / "creator.db")
    token = "admin-token-" + "w" * 32
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    client = TestClient(app)

    too_large = _configure(client, token, "creator-5", "agreement-creator-5-v1", 10001)
    assert too_large.status_code == 422

    first = _configure(client, token, "creator-5", "agreement-creator-5-v1", 1000)
    assert first.status_code == 200
    conflicting = _configure(client, token, "creator-5", "agreement-creator-5-v2", 1000)
    assert conflicting.status_code == 400
    assert "another agreement" in conflicting.json()["detail"]


def test_creator_share_routes_require_admin_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "creator.db"))
    monkeypatch.setenv("MP_ADMIN_TOKEN", "admin-token-" + "q" * 32)
    client = TestClient(app)
    response = client.get("/api/v1/admin/creators/creator-6/revenue-share")
    assert response.status_code == 401
