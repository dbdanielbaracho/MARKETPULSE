from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.api_billing import (
    ApiBillingConfigurationError,
    active_api_plan,
    api_plan_catalog,
    process_api_subscription_event,
)
from app.storage.api_accounts import ApiCustomerStore
from app.storage.api_keys import ApiKeyStore


def _catalog_env(monkeypatch):
    monkeypatch.setenv("MP_API_PRO_PRODUCT_ID", "prod_api_pro")
    monkeypatch.setenv("MP_STRIPE_API_PRO_PRICE_ID", "price_api_pro")
    monkeypatch.setenv("MP_API_PRO_DAILY_LIMIT", "2500")
    monkeypatch.setenv("MP_API_PRO_SCOPES", "markets:read,history:read")


def _subscription_event(event_id: str, customer: str, status: str = "active", event_type: str = "customer.subscription.updated"):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_api_123456",
                "customer": customer,
                "status": status,
                "items": {
                    "data": [{
                        "price": {"product": "prod_api_pro"},
                        "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                    }]
                },
            }
        },
    }


def test_catalog_never_invents_plan_configuration(monkeypatch):
    for name in (
        "MP_API_STARTER_PRODUCT_ID", "MP_STRIPE_API_STARTER_PRICE_ID", "MP_API_STARTER_DAILY_LIMIT", "MP_API_STARTER_SCOPES",
        "MP_API_PRO_PRODUCT_ID", "MP_STRIPE_API_PRO_PRICE_ID", "MP_API_PRO_DAILY_LIMIT", "MP_API_PRO_SCOPES",
        "MP_API_BUSINESS_PRODUCT_ID", "MP_STRIPE_API_BUSINESS_PRICE_ID", "MP_API_BUSINESS_DAILY_LIMIT", "MP_API_BUSINESS_SCOPES",
    ):
        monkeypatch.delenv(name, raising=False)
    assert api_plan_catalog() == {}
    monkeypatch.setenv("MP_API_PRO_PRODUCT_ID", "prod_partial")
    with pytest.raises(ApiBillingConfigurationError, match="incomplete"):
        api_plan_catalog()


def test_verified_events_bind_customer_and_project_active_plan(tmp_path, monkeypatch):
    _catalog_env(monkeypatch)
    catalog = api_plan_catalog()
    store = ApiCustomerStore(str(tmp_path / "app.db"))
    account = store.create(account_id="apiacct_" + "a" * 32, email="api@example.com", raw_token="x" * 40)

    checkout = {
        "id": "evt_checkout123",
        "type": "checkout.session.completed",
        "data": {"object": {"mode": "subscription", "client_reference_id": account.account_id, "customer": "cus_12345678"}},
    }
    assert process_api_subscription_event(checkout, store=store, catalog=catalog) == "customer_bound"
    assert process_api_subscription_event(checkout, store=store, catalog=catalog) == "duplicate"
    assert process_api_subscription_event(_subscription_event("evt_subscription123", "cus_12345678"), store=store, catalog=catalog) == "entitlement_projected"

    plan = active_api_plan(store, account.account_id, catalog)
    assert plan is not None
    assert plan.plan == "pro"
    assert plan.daily_limit == 2500
    assert plan.scopes == ("history:read", "markets:read")


def test_account_owned_key_fails_closed_after_subscription_cancellation(tmp_path, monkeypatch):
    _catalog_env(monkeypatch)
    path = str(tmp_path / "app.db")
    catalog = api_plan_catalog()
    accounts = ApiCustomerStore(path)
    account = accounts.create(account_id="apiacct_" + "b" * 32, email="subscriber@example.com", raw_token="y" * 40)
    process_api_subscription_event(
        {"id": "evt_checkout456", "type": "checkout.session.completed", "data": {"object": {"mode": "subscription", "client_reference_id": account.account_id, "customer": "cus_87654321"}}},
        store=accounts,
        catalog=catalog,
    )
    process_api_subscription_event(_subscription_event("evt_active456", "cus_87654321"), store=accounts, catalog=catalog)

    keys = ApiKeyStore(path)
    raw = "pb_live_" + "z" * 40
    keys.create(
        key_id="key-owned-1",
        raw_token=raw,
        name="subscriber key",
        plan="pro",
        scopes=("markets:read", "history:read"),
        daily_limit=2500,
        owner_account_id=account.account_id,
    )
    principal = keys.authorize(raw, "markets:read")
    assert principal.owner_account_id == account.account_id
    assert principal.usage_today == 1

    canceled = _subscription_event("evt_cancel456", "cus_87654321", status="active", event_type="customer.subscription.deleted")
    process_api_subscription_event(canceled, store=accounts, catalog=catalog)
    assert active_api_plan(accounts, account.account_id, catalog) is None
    with pytest.raises(PermissionError, match="subscription is not active"):
        keys.authorize(raw, "markets:read")


def test_owned_key_fails_closed_if_current_product_mapping_changes(tmp_path, monkeypatch):
    _catalog_env(monkeypatch)
    path = str(tmp_path / "app.db")
    catalog = api_plan_catalog()
    accounts = ApiCustomerStore(path)
    account = accounts.create(account_id="apiacct_" + "c" * 32, email="subscriber@example.com", raw_token="q" * 40)
    accounts.bind_customer(account.account_id, "cus_11111111")
    process_api_subscription_event(_subscription_event("evt_product789", "cus_11111111"), store=accounts, catalog=catalog)
    keys = ApiKeyStore(path)
    raw = "pb_live_" + "m" * 40
    keys.create(key_id="key-owned-2", raw_token=raw, name="key", plan="pro", scopes=("markets:read",), daily_limit=2500, owner_account_id=account.account_id)
    monkeypatch.setenv("MP_API_PRO_PRODUCT_ID", "prod_replaced")
    with pytest.raises(PermissionError, match="subscription is not active"):
        keys.authorize(raw, "markets:read")


def test_customer_binding_collision_fails_closed(tmp_path):
    store = ApiCustomerStore(str(tmp_path / "app.db"))
    first = store.create(account_id="apiacct_" + "d" * 32, email="first@example.com", raw_token="1" * 40)
    second = store.create(account_id="apiacct_" + "e" * 32, email="second@example.com", raw_token="2" * 40)
    store.bind_customer(first.account_id, "cus_collision1")
    with pytest.raises(ValueError, match="already bound"):
        store.bind_customer(second.account_id, "cus_collision1")
