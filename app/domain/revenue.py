from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum


class RevenueState(StrEnum):
    CLICKED = "clicked"
    ATTRIBUTED = "attributed"
    QUALIFIED = "qualified"
    COMMISSION_PENDING = "commission_pending"
    APPROVED = "approved"
    PAYABLE = "payable"
    PAID = "paid"
    REJECTED = "rejected"
    REVERSED = "reversed"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


_ALLOWED_TRANSITIONS: dict[RevenueState, set[RevenueState]] = {
    RevenueState.CLICKED: {RevenueState.ATTRIBUTED, RevenueState.EXPIRED, RevenueState.UNKNOWN},
    RevenueState.ATTRIBUTED: {RevenueState.QUALIFIED, RevenueState.REJECTED, RevenueState.EXPIRED, RevenueState.UNKNOWN},
    RevenueState.QUALIFIED: {RevenueState.COMMISSION_PENDING, RevenueState.REJECTED, RevenueState.DISPUTED},
    RevenueState.COMMISSION_PENDING: {RevenueState.APPROVED, RevenueState.REJECTED, RevenueState.DISPUTED},
    RevenueState.APPROVED: {RevenueState.PAYABLE, RevenueState.REVERSED, RevenueState.DISPUTED},
    RevenueState.PAYABLE: {RevenueState.PAID, RevenueState.REVERSED, RevenueState.DISPUTED},
    RevenueState.PAID: {RevenueState.REVERSED, RevenueState.DISPUTED},
    RevenueState.REJECTED: set(),
    RevenueState.REVERSED: set(),
    RevenueState.EXPIRED: set(),
    RevenueState.DISPUTED: {RevenueState.APPROVED, RevenueState.REJECTED, RevenueState.REVERSED},
    RevenueState.UNKNOWN: {RevenueState.ATTRIBUTED, RevenueState.REJECTED, RevenueState.EXPIRED},
}


@dataclass(frozen=True)
class AttributionRecord:
    attribution_id: str
    click_id: str
    partner_id: str
    venue: str
    country: str
    state: RevenueState = RevenueState.CLICKED
    commission_amount: float | None = None
    currency: str | None = None
    partner_event_id: str | None = None
    updated_at: datetime = datetime.now(timezone.utc)

    def transition(
        self,
        new_state: RevenueState,
        *,
        commission_amount: float | None = None,
        currency: str | None = None,
        partner_event_id: str | None = None,
    ) -> "AttributionRecord":
        if new_state == self.state:
            return self
        if new_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"invalid revenue transition: {self.state} -> {new_state}")
        if commission_amount is not None and commission_amount < 0:
            raise ValueError("commission amount cannot be negative")
        if commission_amount is not None and not currency:
            raise ValueError("currency is required when commission amount is known")
        return replace(
            self,
            state=new_state,
            commission_amount=self.commission_amount if commission_amount is None else commission_amount,
            currency=self.currency if currency is None else currency.upper(),
            partner_event_id=self.partner_event_id if partner_event_id is None else partner_event_id,
            updated_at=datetime.now(timezone.utc),
        )
