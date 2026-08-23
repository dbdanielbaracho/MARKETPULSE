from app.services.social_distribution import channel_readiness


def test_telegram_readiness_requires_bot_token_and_chat_destination(monkeypatch):
    monkeypatch.setenv("MP_SOCIAL_DISTRIBUTION", "true")
    monkeypatch.setenv("MP_TELEGRAM_AUTHORIZED", "true")
    monkeypatch.setenv("MP_TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.delenv("MP_TELEGRAM_CHAT_ID", raising=False)
    result = channel_readiness(
        "telegram",
        country="US",
        editorial_approved=True,
        partner_contract_verified=False,
        paid_or_commercial=False,
    )
    assert result.ready is False
    assert result.credential_configured is False
    assert "credential_not_configured" in result.reasons

    monkeypatch.setenv("MP_TELEGRAM_CHAT_ID", "@predibeacon")
    result = channel_readiness(
        "telegram",
        country="US",
        editorial_approved=True,
        partner_contract_verified=False,
        paid_or_commercial=False,
    )
    assert result.ready is True
    assert result.credential_configured is True
