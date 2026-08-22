from app.domain.revenue import AttributionRecord, RevenueState
from app.storage.revenue import RevenueStore


def sample() -> AttributionRecord:
    return AttributionRecord(
        attribution_id="attr-1",
        click_id="click-1",
        partner_id="partner-approved-by-config",
        venue="kalshi",
        country="US",
    )


def test_click_persistence_is_idempotent(tmp_path):
    store = RevenueStore(str(tmp_path / "revenue.db"))
    first = store.record_click(sample())
    second = store.record_click(sample())
    assert first.attribution_id == second.attribution_id
    assert store.summary()["record_count"] == 1
    assert store.summary()["audit_event_count"] == 1


def test_reconciliation_requires_partner_event_and_is_idempotent(tmp_path):
    store = RevenueStore(str(tmp_path / "revenue.db"))
    store.record_click(sample())
    attributed = store.transition(
        "attr-1", RevenueState.ATTRIBUTED, partner_event_id="partner-event-1"
    )
    duplicate = store.transition(
        "attr-1", RevenueState.ATTRIBUTED, partner_event_id="partner-event-1"
    )
    assert attributed == duplicate
    assert store.summary()["audit_event_count"] == 2


def test_dashboard_never_invents_unknown_commission(tmp_path):
    store = RevenueStore(str(tmp_path / "revenue.db"))
    store.record_click(sample())
    summary = store.summary()
    assert summary["known_commission_totals"] == {}
    assert summary["unpriced_record_count"] == 1
    assert summary["commercial_intake_enabled"] is False
