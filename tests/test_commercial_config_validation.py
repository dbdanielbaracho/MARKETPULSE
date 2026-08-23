import pytest

from app.config.runtime import RuntimeFlags, validate_commercial_partner_config


def test_commercial_verification_requires_partner_identity(monkeypatch):
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.delenv("MP_KALSHI_PARTNER_ID", raising=False)

    with pytest.raises(ValueError, match="MP_KALSHI_PARTNER_ID is required"):
        validate_commercial_partner_config("kalshi")


def test_organic_venue_does_not_require_partner_identity(monkeypatch):
    monkeypatch.setenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", "false")
    monkeypatch.delenv("MP_POLYMARKET_PARTNER_ID", raising=False)

    validate_commercial_partner_config("polymarket")


def test_verified_partner_configuration_is_accepted(monkeypatch):
    monkeypatch.setenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", "true")
    monkeypatch.setenv("MP_POLYMARKET_PARTNER_ID", "poly-affiliate-us")

    validate_commercial_partner_config("polymarket")


def test_runtime_flags_validate_both_partner_claims(monkeypatch):
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.delenv("MP_KALSHI_PARTNER_ID", raising=False)
    monkeypatch.setenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", "false")

    with pytest.raises(ValueError, match="MP_KALSHI_PARTNER_ID is required"):
        RuntimeFlags.from_env()


def test_unknown_commercial_venue_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="unsupported commercial venue"):
        validate_commercial_partner_config("unknown")
