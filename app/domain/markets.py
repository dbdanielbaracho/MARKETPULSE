from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class NormalizedMarket(BaseModel):
    venue: Literal["kalshi", "polymarket"]
    venue_market_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str | None = None
    yes_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    # Lifetime/notional traded volume normalized to USD terms when the provider
    # exposes enough information to do so.
    volume_usd: float | None = Field(default=None, ge=0.0)
    # Provider-reported trailing 24h activity normalized to USD/notional terms.
    # This is deliberately distinct from lifetime volume because public
    # Discovery promises what deserves attention "now".
    volume_24h_usd: float | None = Field(default=None, ge=0.0)
    closes_at: datetime | None = None
    source_url: HttpUrl | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("market title cannot be blank")
        return value

    @field_validator("observed_at")
    @classmethod
    def observed_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return value

    @property
    def canonical_id(self) -> str:
        return f"{self.venue}:{self.venue_market_id}"
