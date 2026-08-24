from datetime import datetime, timedelta, timezone

import pytest

from app.services.pro_entitlements import (
    ALLOWED_PRO_FEATURES,
    PRO_FEATURE_ADVANCED_INTELLIGENCE,
    ProEntitlementStore,
    ProProductConfig,
)
from app.services.pro_stripe_projection import process_verified_subscription_event
from app.storage.pro_accounts import ProAccountStore


ACCOUNT = 'acct_' + 'a' * 32
TOKEN = 'pp_live_' + 'x' * 48
PRODUCT = 'prod_predibeacon_pro'


def _event(event_id, event_type, obj):
    return {'id': event_id, 'type': event_type, 'data': {'object': obj}}


def _subscription(*, customer='cus_customer123', status='active', product=PRODUCT, period_end=None):
    period_end = period_end or int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    return {
        'id': 'sub_subscription123',
        'customer': customer,
        'status': status,
        'items': {'data': [{'price': {'product': product}, 'current_period_end': period_end}]},
    }


def _stores(tmp_path):
    path = str(tmp_path / 'pro-projection.db')
    accounts = ProAccountStore(path)
    accounts.create(account_id=ACCOUNT, email='owner@example.com', raw_token=TOKEN)
    entitlements = ProEntitlementStore(path)
    product = ProProductConfig('stripe', PRODUCT, ALLOWED_PRO_FEATURES)
    return accounts, entitlements, product


def test_checkout_binds_customer_then_subscription_projects_entitlement(tmp_path):
    accounts, entitlements, product = _stores(tmp_path)
    checkout = _event('evt_checkout123', 'checkout.session.completed', {
        'mode': 'subscription',
        'client_reference_id': ACCOUNT,
        'customer': 'cus_customer123',
    })
    assert process_verified_subscription_event(
        checkout, accounts=accounts, entitlements=entitlements, product=product
    ) == 'customer_bound'
    assert accounts.by_customer('cus_customer123').account_id == ACCOUNT

    subscription = _event('evt_subscription123', 'customer.subscription.created', _subscription())
    assert process_verified_subscription_event(
        subscription, accounts=accounts, entitlements=entitlements, product=product
    ) == 'entitlement_projected'
    assert entitlements.has_feature(ACCOUNT, PRO_FEATURE_ADVANCED_INTELLIGENCE, product)

    assert process_verified_subscription_event(
        subscription, accounts=accounts, entitlements=entitlements, product=product
    ) == 'duplicate'


def test_other_product_never_grants_pro_access(tmp_path):
    accounts, entitlements, product = _stores(tmp_path)
    accounts.bind_customer(ACCOUNT, 'cus_customer123')
    outcome = process_verified_subscription_event(
        _event('evt_otherproduct', 'customer.subscription.updated', _subscription(product='prod_other')),
        accounts=accounts,
        entitlements=entitlements,
        product=product,
    )
    assert outcome == 'ignored_other_product'
    assert entitlements.active_features(ACCOUNT, product) == frozenset()


def test_deleted_subscription_revokes_access(tmp_path):
    accounts, entitlements, product = _stores(tmp_path)
    accounts.bind_customer(ACCOUNT, 'cus_customer123')
    process_verified_subscription_event(
        _event('evt_active123', 'customer.subscription.created', _subscription()),
        accounts=accounts, entitlements=entitlements, product=product,
    )
    assert entitlements.active_features(ACCOUNT, product)
    process_verified_subscription_event(
        _event('evt_deleted123', 'customer.subscription.deleted', _subscription(status='active')),
        accounts=accounts, entitlements=entitlements, product=product,
    )
    assert entitlements.active_features(ACCOUNT, product) == frozenset()


def test_unbound_customer_stays_retryable_and_event_is_not_marked(tmp_path):
    accounts, entitlements, product = _stores(tmp_path)
    with pytest.raises(LookupError, match='not bound'):
        process_verified_subscription_event(
            _event('evt_unbound123', 'customer.subscription.updated', _subscription(customer='cus_unknown123')),
            accounts=accounts, entitlements=entitlements, product=product,
        )
    assert accounts.event_seen('evt_unbound123') is False


def test_malformed_subscription_is_not_marked_processed(tmp_path):
    accounts, entitlements, product = _stores(tmp_path)
    accounts.bind_customer(ACCOUNT, 'cus_customer123')
    with pytest.raises(ValueError):
        process_verified_subscription_event(
            _event('evt_malformed123', 'customer.subscription.updated', {
                'id': 'sub_subscription123', 'customer': 'cus_customer123', 'status': 'active', 'items': {'data': []}
            }),
            accounts=accounts, entitlements=entitlements, product=product,
        )
    assert accounts.event_seen('evt_malformed123') is False
