from fastapi.testclient import TestClient

from app.entrypoint import app
from app.storage.creator_agreements import CreatorAgreementStore


client = TestClient(app)


def _headers(token: str) -> dict[str, str]:
    return {"X-MarketPulse-Admin-Token": token}


def test_creator_agreement_admin_lifecycle_is_explicit_and_protected(tmp_path, monkeypatch):
    path = str(tmp_path / "creator-agreement-admin.db")
    token = "admin-" + "x" * 40
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)

    denied = client.post(
        "/api/v1/admin/creators/creator-a/agreement",
        json={"agreement_id": "agreement-a", "share_basis_points": 2500},
    )
    assert denied.status_code == 401

    configured = client.post(
        "/api/v1/admin/creators/creator-a/agreement",
        headers=_headers(token),
        json={"agreement_id": "agreement-a", "share_basis_points": 2500},
    )
    assert configured.status_code == 200
    assert configured.json()["approved"] is False
    assert "share_basis_points" not in configured.text
    stored = CreatorAgreementStore(path).for_creator("creator-a")
    assert stored is not None and stored.approved is False

    wrong = client.post(
        "/api/v1/admin/creators/creator-a/agreement/approve",
        headers=_headers(token),
        json={"agreement_id": "agreement-other"},
    )
    assert wrong.status_code == 400
    assert CreatorAgreementStore(path).approved_for_creator("creator-a") is None

    approved = client.post(
        "/api/v1/admin/creators/creator-a/agreement/approve",
        headers=_headers(token),
        json={"agreement_id": "agreement-a"},
    )
    assert approved.status_code == 200
    assert approved.json()["approved"] is True
    assert "share_basis_points" not in approved.text
    assert CreatorAgreementStore(path).approved_for_creator("creator-a") is not None

    revoked = client.post(
        "/api/v1/admin/creators/creator-a/agreement/revoke",
        headers=_headers(token),
    )
    assert revoked.status_code == 200
    assert revoked.json() == {"creator_id": "creator-a", "approved": False}
    assert CreatorAgreementStore(path).approved_for_creator("creator-a") is None


def test_creator_agreement_admin_rejects_invalid_configuration(tmp_path, monkeypatch):
    path = str(tmp_path / "creator-agreement-invalid.db")
    token = "admin-" + "y" * 40
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)

    invalid = client.post(
        "/api/v1/admin/creators/creator-a/agreement",
        headers=_headers(token),
        json={"agreement_id": "agreement-a", "share_basis_points": 10001},
    )
    assert invalid.status_code == 422

    missing = client.post(
        "/api/v1/admin/creators/creator-missing/agreement/approve",
        headers=_headers(token),
        json={"agreement_id": "agreement-missing"},
    )
    assert missing.status_code == 404
