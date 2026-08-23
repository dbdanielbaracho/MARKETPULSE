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
    monkeypatch.setenv("MP_POLYMARKET_PARTNER_ID", "poly-affiliate_us:2026.08")

    validate_commercial_partner_config("polymarket")


@pytest.mark.parametrize(
    "partner_id",
    [
        "contains space",
        "line\nbreak",
        "html<script>",
        "query?partner=1",
        "x" * 201,
    ],
)
def test_partner_identity_is_bounded_and_allowlisted_even_before_activation(monkeypatch, partner_id):
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "false")
    monkeypatch.setenv("MP_KALSHI_PARTNER_ID", partner_id)

    with pytest.raises(ValueError, match="MP_KALSHI_PARTNER_ID must be 1-200 characters"):
        validate_commercial_partner_config("kalshi")


def test_runtime_flags_validate_both_partner_claims(monkeypatch):
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.delenv("MP_KALSHI_PARTNER_ID", raising=False)
    monkeypatch.setenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", "false")

    with pytest.raises(ValueError, match="MP_KALSHI_PARTNER_ID is required"):
        RuntimeFlags.from_env()


def test_runtime_flags_reject_invalid_latent_partner_identity(monkeypatch):
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "false")
    monkeypatch.setenv("MP_KALSHI_PARTNER_ID", "bad/value")
    monkeypatch.setenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", "false")
    monkeypatch.delenv("MP_POLYMARKET_PARTNER_ID", raising=False)

    with pytest.raises(ValueError, match="MP_KALSHI_PARTNER_ID must be 1-200 characters"):
        RuntimeFlags.from_env()


def test_unknown_commercial_venue_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="unsupported commercial venue"):
        validate_commercial_partner_config("unknown")
