from datetime import datetime, timedelta, timezone

import pytest

from app.services.pro_entitlements import (
    ALLOWED_PRO_FEATURES,
    PRO_FEATURE_ADVANCED_INTELLIGENCE,
    ProEntitlementStore,
    ProProductConfig,
    ProviderEntitlementState,
    normalize_provider_features,
)


def config() -> ProProductConfig:
    return ProProductConfig("stripe", "prod_predibeacon_pro", ALLOWED_PRO_FEATURES)


def state(*, status: str = "active", product_id: str = "prod_predibeacon_pro", valid_until=None):
    return ProviderEntitlementState(
        subject_id="user-123",
        product_id=product_id,
        subscription_id="sub-123",
        status=status,
        valid_until=valid_until,
    )


def test_unconfigured_billing_fails_closed(tmp_path):
    store = ProEntitlementStore(tmp_path / "pro.sqlite")
    store.upsert_provider_state(state())
    assert store.active_features("user-123", None) == frozenset()
    assert not store.has_feature("user-123", PRO_FEATURE_ADVANCED_INTELLIGENCE, None)


def test_active_matching_product_grants_configured_features(tmp_path):
    store = ProEntitlementStore(tmp_path / "pro.sqlite")
    store.upsert_provider_state(state())
    assert PRO_FEATURE_ADVANCED_INTELLIGENCE in store.active_features("user-123", config())


@pytest.mark.parametrize("status", ["incomplete", "past_due", "unpaid", "canceled", "paused", "unknown"])
def test_non_access_subscription_statuses_fail_closed(tmp_path, status):
    store = ProEntitlementStore(tmp_path / f"{status}.sqlite")
    store.upsert_provider_state(state(status=status))
    assert store.active_features("user-123", config()) == frozenset()


def test_trialing_subscription_is_explicitly_access_granting(tmp_path):
    store = ProEntitlementStore(tmp_path / "trial.sqlite")
    store.upsert_provider_state(state(status="trialing"))
    assert store.has_feature("user-123", PRO_FEATURE_ADVANCED_INTELLIGENCE, config())


def test_product_mismatch_never_grants_access(tmp_path):
    store = ProEntitlementStore(tmp_path / "mismatch.sqlite")
    store.upsert_provider_state(state(product_id="prod_other"))
    assert store.active_features("user-123", config()) == frozenset()


def test_expired_entitlement_fails_closed(tmp_path):
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    store = ProEntitlementStore(tmp_path / "expired.sqlite")
    store.upsert_provider_state(state(valid_until=now - timedelta(seconds=1)))
    assert store.active_features("user-123", config(), now=now) == frozenset()


def test_future_entitlement_grants_access(tmp_path):
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    store = ProEntitlementStore(tmp_path / "future.sqlite")
    store.upsert_provider_state(state(valid_until=now + timedelta(days=30)))
    assert store.has_feature("user-123", PRO_FEATURE_ADVANCED_INTELLIGENCE, config(), now=now)


def test_naive_provider_expiry_is_rejected(tmp_path):
    store = ProEntitlementStore(tmp_path / "naive.sqlite")
    with pytest.raises(ValueError, match="timezone-aware"):
        store.upsert_provider_state(state(valid_until=datetime(2026, 8, 24)))


def test_unknown_feature_fails_closed(tmp_path):
    store = ProEntitlementStore(tmp_path / "feature.sqlite")
    store.upsert_provider_state(state())
    assert not store.has_feature("user-123", "invented_feature", config())


def test_provider_feature_validation_rejects_unknown_capabilities():
    with pytest.raises(ValueError, match="unsupported Pro feature"):
        normalize_provider_features([PRO_FEATURE_ADVANCED_INTELLIGENCE, "hidden_partner_economics"])


def test_environment_configuration_never_requires_a_price(monkeypatch):
    monkeypatch.setenv("MP_PRO_PRODUCT_ID", "prod_live_123")
    monkeypatch.delenv("MP_PRO_FEATURES", raising=False)
    monkeypatch.delenv("MP_PRO_BILLING_PROVIDER", raising=False)
    parsed = ProProductConfig.from_env()
    assert parsed is not None
    assert parsed.provider == "stripe"
    assert parsed.product_id == "prod_live_123"
    assert parsed.features == ALLOWED_PRO_FEATURES


def test_environment_configuration_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setenv("MP_PRO_PRODUCT_ID", "prod_live_123")
    monkeypatch.setenv("MP_PRO_BILLING_PROVIDER", "invented")
    with pytest.raises(ValueError, match="must be stripe"):
        ProProductConfig.from_env()
