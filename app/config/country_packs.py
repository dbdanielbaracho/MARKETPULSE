from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml


@dataclass(frozen=True)
class CountryPackPolicy:
    audience: str
    commercial_outbound_allowed: bool
    paid_social_allowed: bool
    minimum_age: int
    route_mode: str
    reason: str


@dataclass(frozen=True)
class CountryPack:
    country_code: str
    locale: str
    currency: str
    enabled: bool
    discovery_enabled: bool
    outbound_enabled: bool
    automated_content_enabled: bool
    venues: Mapping[str, Mapping[str, bool]]
    policy: CountryPackPolicy


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = _ROOT / "config" / "countries"
_TOP_LEVEL_KEYS = {
    "version",
    "country_code",
    "locale",
    "currency",
    "enabled",
    "features",
    "venues",
    "policy",
}
_FEATURE_KEYS = {"discovery", "outbound", "automated_content"}
_POLICY_KEYS = {
    "audience",
    "commercial_outbound_allowed",
    "paid_social_allowed",
    "minimum_age",
    "route_mode",
    "reason",
}
_VENUE_KEYS = {"discovery_enabled", "outbound_enabled"}


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return dict(value)


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _text(value: object, name: str, *, max_length: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise ValueError(f"{name} is invalid")
    return normalized


def _exact_keys(data: Mapping[str, object], allowed: set[str], name: str) -> None:
    unexpected = set(data) - allowed
    if unexpected:
        raise ValueError(f"{name} contains unsupported keys: {sorted(unexpected)}")


def load_country_pack(path: Path) -> CountryPack:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = _mapping(raw, f"country pack {path.name}")
    _exact_keys(data, _TOP_LEVEL_KEYS, f"country pack {path.name}")
    if data.get("version") != 1:
        raise ValueError(f"country pack {path.name} version must be 1")

    country_code = _text(data.get("country_code"), "country_code", max_length=2).upper()
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValueError("country_code must be an ISO-style two-letter code")
    locale = _text(data.get("locale"), "locale", max_length=20)
    currency = _text(data.get("currency"), "currency", max_length=3).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a three-letter code")
    enabled = _bool(data.get("enabled"), "enabled")

    features = _mapping(data.get("features"), "features")
    _exact_keys(features, _FEATURE_KEYS, "features")
    if set(features) != _FEATURE_KEYS:
        raise ValueError("features must define discovery, outbound and automated_content")

    venue_config = _mapping(data.get("venues", {}), "venues")
    venues: dict[str, Mapping[str, bool]] = {}
    for venue, raw_settings in venue_config.items():
        if not isinstance(venue, str) or not venue.strip():
            raise ValueError("venue name is invalid")
        settings = _mapping(raw_settings, f"venue {venue}")
        _exact_keys(settings, _VENUE_KEYS, f"venue {venue}")
        if set(settings) != _VENUE_KEYS:
            raise ValueError(f"venue {venue} must define discovery_enabled and outbound_enabled")
        venues[venue.casefold()] = {
            "discovery_enabled": _bool(settings["discovery_enabled"], f"{venue}.discovery_enabled"),
            "outbound_enabled": _bool(settings["outbound_enabled"], f"{venue}.outbound_enabled"),
        }

    policy_data = _mapping(data.get("policy"), "policy")
    _exact_keys(policy_data, _POLICY_KEYS, "policy")
    if set(policy_data) != _POLICY_KEYS:
        raise ValueError("policy is incomplete")
    minimum_age = policy_data.get("minimum_age")
    if isinstance(minimum_age, bool) or not isinstance(minimum_age, int) or minimum_age < 0 or minimum_age > 120:
        raise ValueError("policy.minimum_age is invalid")
    policy = CountryPackPolicy(
        audience=_text(policy_data.get("audience"), "policy.audience"),
        commercial_outbound_allowed=_bool(
            policy_data.get("commercial_outbound_allowed"),
            "policy.commercial_outbound_allowed",
        ),
        paid_social_allowed=_bool(policy_data.get("paid_social_allowed"), "policy.paid_social_allowed"),
        minimum_age=minimum_age,
        route_mode=_text(policy_data.get("route_mode"), "policy.route_mode", max_length=60),
        reason=_text(policy_data.get("reason"), "policy.reason"),
    )

    discovery_enabled = _bool(features["discovery"], "features.discovery")
    outbound_enabled = _bool(features["outbound"], "features.outbound")
    automated_content_enabled = _bool(features["automated_content"], "features.automated_content")

    # A disabled country pack can never activate a side effect by child configuration.
    if not enabled and (discovery_enabled or outbound_enabled or automated_content_enabled):
        raise ValueError("disabled country pack cannot enable feature side effects")
    if not outbound_enabled and any(settings["outbound_enabled"] for settings in venues.values()):
        raise ValueError("venue outbound cannot be enabled when country outbound is disabled")
    if not policy.commercial_outbound_allowed and any(settings["outbound_enabled"] for settings in venues.values()):
        raise ValueError("venue outbound cannot bypass country commercial policy")

    return CountryPack(
        country_code=country_code,
        locale=locale,
        currency=currency,
        enabled=enabled,
        discovery_enabled=discovery_enabled,
        outbound_enabled=outbound_enabled,
        automated_content_enabled=automated_content_enabled,
        venues=venues,
        policy=policy,
    )


@lru_cache(maxsize=1)
def country_packs() -> Mapping[str, CountryPack]:
    packs: dict[str, CountryPack] = {}
    for path in sorted(_DEFAULT_DIR.glob("*.yaml")):
        pack = load_country_pack(path)
        if pack.country_code in packs:
            raise ValueError(f"duplicate country pack: {pack.country_code}")
        packs[pack.country_code] = pack
    if "US" not in packs or not packs["US"].enabled:
        raise ValueError("enabled US country pack is required")
    return packs


def country_pack(country: str | None) -> CountryPack | None:
    if country is None:
        return None
    normalized = country.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        return None
    return country_packs().get(normalized)
