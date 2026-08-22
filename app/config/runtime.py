from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"invalid boolean environment value for {name}")


@dataclass(frozen=True)
class RuntimeFlags:
    kalshi_ingestion: bool
    polymarket_ingestion: bool
    automated_publishing: bool
    outbound_routing: bool
    social_distribution: bool

    @classmethod
    def from_env(cls) -> "RuntimeFlags":
        # External side effects default OFF. Public-data ingestion defaults ON.
        return cls(
            kalshi_ingestion=_flag("MP_KALSHI_INGESTION", True),
            polymarket_ingestion=_flag("MP_POLYMARKET_INGESTION", True),
            automated_publishing=_flag("MP_AUTOMATED_PUBLISHING", False),
            outbound_routing=_flag("MP_OUTBOUND_ROUTING", False),
            social_distribution=_flag("MP_SOCIAL_DISTRIBUTION", False),
        )

    def venue_enabled(self, venue: str) -> bool:
        normalized = venue.casefold()
        if normalized == "kalshi":
            return self.kalshi_ingestion
        if normalized == "polymarket":
            return self.polymarket_ingestion
        return False
