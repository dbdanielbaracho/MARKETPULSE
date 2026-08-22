import pytest

from app.domain.revenue import AttributionRecord, RevenueState
from app.services.outbound import PartnerRoute, resolve_outbound


def test_outbound_fails_closed_without_verified_route():
    decision = resolve_outbound(
        venue="kalshi",
        country="US",
        routes=[PartnerRoute("k", "kalshi", "US", "https://kalshi.com/markets/x", enabled=True)],
    )
    assert decision.allowed is False
    assert decision.reason == "no_verified_route"


def test_outbound_rejects_untrusted_host_even_when_enabled():
    decision = resolve_outbound(
        venue="kalshi",
        country="US",
        routes=[PartnerRoute("k", "kalshi", "US", "https://evil.example/phish", enabled=True, commercial_verified=True, allowed_hosts=("kalshi.com",))],
    )
    assert decision.allowed is False


def test_outbound_accepts_server_side_https_allowlist():
    decision = resolve_outbound(
        venue="kalshi",
        country="US",
        routes=[PartnerRoute("k", "kalshi", "US", "https://kalshi.com/markets/x", enabled=True, commercial_verified=True, allowed_hosts=("kalshi.com",))],
    )
    assert decision.allowed is True
    assert decision.partner_id == "k"


def test_revenue_happy_path_and_amount_requires_currency():
    record = AttributionRecord("a1", "c1", "p1", "kalshi", "US")
    record = record.transition(RevenueState.ATTRIBUTED)
    record = record.transition(RevenueState.QUALIFIED)
    record = record.transition(RevenueState.COMMISSION_PENDING)
    with pytest.raises(ValueError):
        record.transition(RevenueState.APPROVED, commission_amount=12.50)
    record = record.transition(RevenueState.APPROVED, commission_amount=12.50, currency="usd")
    record = record.transition(RevenueState.PAYABLE)
    record = record.transition(RevenueState.PAID)
    assert record.state is RevenueState.PAID
    assert record.commission_amount == 12.50
    assert record.currency == "USD"


def test_invalid_revenue_transition_fails_closed():
    record = AttributionRecord("a1", "c1", "p1", "kalshi", "US")
    with pytest.raises(ValueError):
        record.transition(RevenueState.PAID)


def test_duplicate_state_is_idempotent():
    record = AttributionRecord("a1", "c1", "p1", "kalshi", "US")
    assert record.transition(RevenueState.CLICKED) is record
