from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.partners import RevenueRecord, RevenueState


_ALLOWED_TRANSITIONS: dict[RevenueState, set[RevenueState]] = {
    RevenueState.UNKNOWN: {RevenueState.PENDING, RevenueState.REJECTED},
    RevenueState.PENDING: {RevenueState.APPROVED, RevenueState.REJECTED, RevenueState.EXPIRED, RevenueState.DISPUTED},
    RevenueState.APPROVED: {RevenueState.PAYABLE, RevenueState.REVERSED, RevenueState.DISPUTED},
    RevenueState.PAYABLE: {RevenueState.PAID, RevenueState.REVERSED, RevenueState.DISPUTED},
    RevenueState.PAID: {RevenueState.REVERSED, RevenueState.DISPUTED},
    RevenueState.DISPUTED: {RevenueState.APPROVED, RevenueState.REJECTED, RevenueState.REVERSED},
    RevenueState.REJECTED: set(),
    RevenueState.EXPIRED: set(),
    RevenueState.REVERSED: set(),
}


def validate_transition(current: RevenueState, new: RevenueState) -> None:
    if new == current:
        return
    if new not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid revenue transition: {current} -> {new}")


@dataclass
class RevenueLedger:
    """In-memory deterministic ledger core; persistence adapter is intentionally separate."""
    records: dict[str, RevenueRecord] = field(default_factory=dict)
    partner_event_index: dict[str, str] = field(default_factory=dict)

    def apply(self, record: RevenueRecord) -> RevenueRecord:
        existing_id = self.partner_event_index.get(record.source_event_id)
        if existing_id and existing_id != record.revenue_id:
            raise ValueError("source event already attributed to another revenue record")

        existing = self.records.get(record.revenue_id)
        if existing:
            if existing.partner_reference != record.partner_reference or existing.venue != record.venue:
                raise ValueError("revenue identity fields cannot change")
            validate_transition(existing.state, record.state)

        self.records[record.revenue_id] = record
        self.partner_event_index[record.source_event_id] = record.revenue_id
        return record

    def totals(self) -> dict[RevenueState, float]:
        result = {state: 0.0 for state in RevenueState}
        for record in self.records.values():
            if record.amount is not None:
                result[record.state] += record.amount
        return result
