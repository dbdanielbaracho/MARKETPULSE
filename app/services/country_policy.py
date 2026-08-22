from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CountryPolicy:
    country: str
    audience: str
    informational_content_allowed: bool
    commercial_outbound_allowed: bool
    paid_social_allowed: bool
    minimum_age: int
    route_mode: str
    reason: str


_POLICIES: Mapping[str, CountryPolicy] = {
    "US": CountryPolicy(
        country="US",
        audience="us_global",
        informational_content_allowed=True,
        commercial_outbound_allowed=False,
        paid_social_allowed=False,
        minimum_age=18,
        route_mode="contract_required",
        reason="partner_contract_and_platform_ad_authorization_pending",
    ),
    "BR": CountryPolicy(
        country="BR",
        audience="brazil_informational",
        informational_content_allowed=True,
        commercial_outbound_allowed=False,
        paid_social_allowed=False,
        minimum_age=18,
        route_mode="informational_only",
        reason="direct_commercial_promotion_not_authorized",
    ),
}
_UNKNOWN = CountryPolicy(
    country="ZZ",
    audience="global_informational",
    informational_content_allowed=True,
    commercial_outbound_allowed=False,
    paid_social_allowed=False,
    minimum_age=18,
    route_mode="informational_only",
    reason="country_or_eligibility_not_verified",
)


def resolve_country_policy(country: str | None) -> CountryPolicy:
    if country is None:
        return _UNKNOWN
    normalized = country.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        return _UNKNOWN
    return _POLICIES.get(normalized, _UNKNOWN)


def commercial_action_allowed(
    *,
    country: str | None,
    age: int | None,
    partner_contract_verified: bool,
    platform_authorization_verified: bool,
) -> tuple[bool, str]:
    policy = resolve_country_policy(country)
    if age is None or age < policy.minimum_age:
        return False, "age_not_verified"
    if not policy.commercial_outbound_allowed:
        return False, policy.reason
    if not partner_contract_verified:
        return False, "partner_contract_not_verified"
    if not platform_authorization_verified:
        return False, "platform_authorization_not_verified"
    return True, "verified_commercial_action"
