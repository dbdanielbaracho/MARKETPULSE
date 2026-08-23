from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProFeature(StrEnum):
    ADVANCED_ALERTS = "advanced_alerts"
    EXTENDED_HISTORY = "extended_history"
    ADVANCED_SIGNALS = "advanced_signals"
    EXPORTS = "exports"


@dataclass(frozen=True)
class ProPackage:
    code: str
    name: str
    features: tuple[ProFeature, ...]


PRO_PACKAGE = ProPackage(
    code="pro",
    name="PrediBeacon Pro",
    features=(
        ProFeature.ADVANCED_ALERTS,
        ProFeature.EXTENDED_HISTORY,
        ProFeature.ADVANCED_SIGNALS,
        ProFeature.EXPORTS,
    ),
)


def has_entitlement(active_entitlements: set[str] | frozenset[str], feature: ProFeature) -> bool:
    """Fail closed: access exists only for an explicit active feature entitlement."""
    return feature.value in active_entitlements
