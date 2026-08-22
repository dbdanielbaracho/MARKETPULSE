from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class RevenueState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAYABLE = "payable"
    PAID = "paid"
    REVERSED = "reversed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class OutboundDecision(BaseModel):
    allowed: bool
    venue: Literal["kalshi", "polymarket"]
    destination_url: HttpUrl | None = None
    reason: str = Field(min_length=1)
    partner_program: str | None = None

    @model_validator(mode="after")
    def allowed_requires_destination_and_program(self) -> "OutboundDecision":
        if self.allowed and (self.destination_url is None or not self.partner_program):
            raise ValueError("allowed outbound requires destination_url and partner_program")
        return self


class AttributionEvent(BaseModel):
    event_id: str = Field(min_length=8)
    click_id: str = Field(min_length=8)
    partner_event_id: str | None = None
    venue: Literal["kalshi", "polymarket"]
    event_type: str = Field(min_length=1)
    occurred_at: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevenueRecord(BaseModel):
    revenue_id: str = Field(min_length=8)
    venue: Literal["kalshi", "polymarket"]
    partner_reference: str = Field(min_length=1)
    state: RevenueState
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime
    source_event_id: str = Field(min_length=8)

    @model_validator(mode="after")
    def amount_and_currency_are_paired(self) -> "RevenueRecord":
        if (self.amount is None) != (self.currency is None):
            raise ValueError("amount and currency must be provided together")
        return self
