import pytest

from app.services.social_distribution import all_channel_readiness, channel_readiness


@pytest.mark.parametrize("channel", ["instagram", "tiktok", "youtube", "telegram", "whatsapp", "x"])
def test_every_channel_fails_closed_by_default(monkeypatch, channel):
    monkeypatch.delenv("MP_SOCIAL_DISTRIBUTION", raising=False)

    result = channel_readiness(
        channel,
        country="US",
        editorial_approved=False,
        partner_contract_verified=False,
        paid_or_commercial=False,
    )

    assert result.ready is False
    assert "global_social_kill_switch_off" in result.reasons
    assert "credential_not_configured" in result.reasons
    assert "platform_authorization_not_verified" in result.reasons
    assert "editorial_approval_required" in result.reasons


def test_credentials_alone_never_enable_social_distribution(monkeypatch):
    monkeypatch.setenv("MP_SOCIAL_DISTRIBUTION", "true")
    monkeypatch.setenv("MP_INSTAGRAM_ACCESS_TOKEN", "configured-not-real")
    monkeypatch.setenv("MP_INSTAGRAM_AUTHORIZED", "true")

    result = channel_readiness(
        "instagram",
        country="US",
        editorial_approved=False,
        partner_contract_verified=True,
        paid_or_commercial=False,
    )

    assert result.ready is False
    assert result.reasons == ("editorial_approval_required",)


def test_commercial_social_remains_blocked_by_contract_and_country_policy(monkeypatch):
    monkeypatch.setenv("MP_SOCIAL_DISTRIBUTION", "true")
    monkeypatch.setenv("MP_TIKTOK_ACCESS_TOKEN", "configured-not-real")
    monkeypatch.setenv("MP_TIKTOK_AUTHORIZED", "true")

    result = channel_readiness(
        "tiktok",
        country="BR",
        editorial_approved=True,
        partner_contract_verified=False,
        paid_or_commercial=True,
    )

    assert result.ready is False
    assert "partner_contract_not_verified" in result.reasons
    assert "direct_commercial_promotion_not_authorized" in result.reasons


def test_readiness_inventory_contains_every_planned_channel():
    assert {item.channel for item in all_channel_readiness()} == {
        "instagram",
        "tiktok",
        "youtube",
        "telegram",
        "whatsapp",
        "x",
    }


def test_unknown_channel_is_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        channel_readiness(
            "unknown",
            country="US",
            editorial_approved=True,
            partner_contract_verified=True,
            paid_or_commercial=False,
        )
