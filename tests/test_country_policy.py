from pathlib import Path

import pytest
import yaml

from app.services.country_policy import (
    _parse_policy,
    commercial_action_allowed,
    configured_country_policies,
    resolve_country_policy,
)


def test_us_policy_is_informational_until_contract_and_ad_authorization():
    policy = resolve_country_policy("us")

    assert policy.country == "US"
    assert policy.locale == "en-US"
    assert policy.currency == "USD"
    assert policy.default_timezone == "America/New_York"
    assert policy.audience == "us_global"
    assert policy.informational_content_allowed is True
    assert policy.commercial_outbound_allowed is False
    assert policy.paid_social_allowed is False
    assert policy.route_mode == "contract_required"


def test_uk_policy_is_present_but_commercially_fail_closed():
    policy = resolve_country_policy("gb")

    assert policy.country == "GB"
    assert policy.locale == "en-GB"
    assert policy.currency == "GBP"
    assert policy.default_timezone == "Europe/London"
    assert policy.audience == "uk_informational"
    assert policy.informational_content_allowed is True
    assert policy.commercial_outbound_allowed is False
    assert policy.paid_social_allowed is False
    assert policy.route_mode == "informational_only"
    assert policy.reason == "country_pack_disabled_and_commercial_route_not_authorized"


def test_brazil_policy_is_informational_only():
    policy = resolve_country_policy("BR")

    assert policy.country == "BR"
    assert policy.locale == "pt-BR"
    assert policy.currency == "BRL"
    assert policy.default_timezone == "America/Sao_Paulo"
    assert policy.audience == "brazil_informational"
    assert policy.informational_content_allowed is True
    assert policy.commercial_outbound_allowed is False
    assert policy.paid_social_allowed is False
    assert policy.route_mode == "informational_only"


def test_unknown_or_invalid_country_fails_closed():
    for value in (None, "", "USA", "1", "XX"):
        policy = resolve_country_policy(value)
        assert policy.country == "ZZ"
        assert policy.locale == "en-US"
        assert policy.currency == "USD"
        assert policy.default_timezone == "UTC"
        assert policy.commercial_outbound_allowed is False
        assert policy.paid_social_allowed is False
        assert policy.reason == "country_or_eligibility_not_verified"


def test_every_country_pack_has_valid_presentation_boundaries():
    policies = configured_country_policies()
    assert set(policies) == {"BR", "GB", "US"}
    for policy in policies.values():
        assert policy.locale
        assert len(policy.currency) == 3
        assert "/" in policy.default_timezone


def test_country_pack_rejects_invalid_locale_currency_or_timezone():
    source = Path("invalid.yaml")
    base = yaml.safe_load((Path("config/countries/us.yaml")).read_text(encoding="utf-8"))

    invalid_locale = dict(base, locale="english_US")
    with pytest.raises(ValueError, match="BCP 47"):
        _parse_policy(invalid_locale, source)

    invalid_currency = dict(base, currency="dollars")
    with pytest.raises(ValueError, match="currency"):
        _parse_policy(invalid_currency, source)

    invalid_timezone = dict(base, default_timezone="EST")
    with pytest.raises(ValueError, match="IANA timezone"):
        _parse_policy(invalid_timezone, source)


def test_commercial_action_requires_age_country_contract_and_platform_authorization():
    assert commercial_action_allowed(
        country="US",
        age=None,
        partner_contract_verified=True,
        platform_authorization_verified=True,
    ) == (False, "age_not_verified")

    allowed, reason = commercial_action_allowed(
        country="US",
        age=25,
        partner_contract_verified=True,
        platform_authorization_verified=True,
    )
    assert allowed is False
    assert reason == "partner_contract_and_platform_ad_authorization_pending"

    allowed, reason = commercial_action_allowed(
        country="GB",
        age=25,
        partner_contract_verified=True,
        platform_authorization_verified=True,
    )
    assert allowed is False
    assert reason == "country_pack_disabled_and_commercial_route_not_authorized"

    allowed, reason = commercial_action_allowed(
        country="BR",
        age=25,
        partner_contract_verified=True,
        platform_authorization_verified=True,
    )
    assert allowed is False
    assert reason == "direct_commercial_promotion_not_authorized"
