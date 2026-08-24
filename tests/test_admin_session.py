from __future__ import annotations

import os

from app.services.admin_session import issue_session, read_session, verify_credentials, verify_totp


def _configure(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("MP_ADMIN_PASSWORD", "correct horse battery staple")
    monkeypatch.setenv("MP_ADMIN_TOKEN", "x" * 40)
    monkeypatch.setenv("MP_ADMIN_SESSION_SECRET", "s" * 40)
    monkeypatch.delenv("MP_ADMIN_TOTP_SECRET", raising=False)


def test_admin_credentials_use_email_and_password(monkeypatch):
    _configure(monkeypatch)
    assert verify_credentials("OWNER@example.com", "correct horse battery staple")
    assert not verify_credentials("other@example.com", "correct horse battery staple")
    assert not verify_credentials("owner@example.com", "wrong password")


def test_signed_session_round_trip_and_expiry(monkeypatch):
    _configure(monkeypatch)
    token = issue_session("owner@example.com", now=1_000)
    session = read_session(token, now=1_100)
    assert session is not None
    assert session["email"] == "owner@example.com"
    assert read_session(token, now=1_000 + 8 * 60 * 60 + 1) is None


def test_signed_session_rejects_tampering(monkeypatch):
    _configure(monkeypatch)
    token = issue_session("owner@example.com", now=1_000)
    body, signature = token.split(".")
    assert read_session(body + "." + ("A" if signature[0] != "A" else "B") + signature[1:], now=1_100) is None


def test_totp_is_optional_until_secret_is_configured(monkeypatch):
    _configure(monkeypatch)
    assert verify_totp(None, now=1_000)


def test_legacy_admin_token_can_bootstrap_password(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_EMAIL", "admin@predibeacon.com")
    monkeypatch.delenv("MP_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("MP_ADMIN_TOKEN", "legacy-admin-token-which-is-at-least-32-chars")
    monkeypatch.delenv("MP_ADMIN_TOTP_SECRET", raising=False)
    assert verify_credentials("admin@predibeacon.com", os.environ["MP_ADMIN_TOKEN"])
