import pytest
from fastapi import HTTPException

from app.main import _admin_review_configured, _require_admin


def test_admin_review_fails_closed_when_not_configured(monkeypatch):
    monkeypatch.delenv("MP_ADMIN_TOKEN", raising=False)

    assert _admin_review_configured() is False
    with pytest.raises(HTTPException) as error:
        _require_admin(None)
    assert error.value.status_code == 503


def test_admin_review_uses_constant_time_secret_gate(monkeypatch):
    secret = "a" * 32
    monkeypatch.setenv("MP_ADMIN_TOKEN", secret)

    assert _admin_review_configured() is True
    with pytest.raises(HTTPException) as error:
        _require_admin("wrong")
    assert error.value.status_code == 401
    assert _require_admin(secret) is None


def test_short_admin_secret_is_treated_as_unconfigured(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_TOKEN", "too-short")

    assert _admin_review_configured() is False
    with pytest.raises(HTTPException) as error:
        _require_admin("too-short")
    assert error.value.status_code == 503
