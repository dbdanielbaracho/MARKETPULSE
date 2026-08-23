from __future__ import annotations

import os
import re
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}
_PARTNER_ID = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


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


def validate_commercial_partner_config(venue: str) -> None:
    """Fail closed when evidence-bearing commercial configuration is invalid.

    Commercial verification is an evidence-bearing claim. Organic routing may
    exist with no partner identity, but a commercially verified venue requires
    an opaque partner identity whose syntax is bounded and allowlisted. The
    identity itself must never be rendered into public product surfaces except
    where a provider contract explicitly requires it inside the server-created
    outbound destination.
    """
    normalized = venue.strip().upper()
    if normalized not in {"KALSHI", "POLYMARKET"}:
        raise ValueError(f"unsupported commercial venue: {venue}")
    verified = _flag(f"MP_{normalized}_COMMERCIAL_VERIFIED", False)
    partner_id = os.getenv(f"MP_{normalized}_PARTNER_ID", "").strip()
    if verified and not partner_id:
        raise ValueError(
            f"MP_{normalized}_PARTNER_ID is required when MP_{normalized}_COMMERCIAL_VERIFIED is enabled"
        )
    if partner_id and not _PARTNER_ID.fullmatch(partner_id):
        raise ValueError(
            f"MP_{normalized}_PARTNER_ID must be 1-200 characters using only letters, digits, dot, underscore, colon, or hyphen"
        )


@dataclass(frozen=True)
class RuntimeFlags:
    kalshi_ingestion: bool
    polymarket_ingestion: bool
    automated_publishing: bool
    outbound_routing: bool
    social_distribution: bool

    @classmethod
    def from_env(cls) -> "RuntimeFlags":
        # Validate evidence-bearing commercial claims before runtime features start.
        validate_commercial_partner_config("kalshi")
        validate_commercial_partner_config("polymarket")
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
