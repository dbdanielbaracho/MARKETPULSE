from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routes.pro_account_billing as routes
from app.entrypoint import app
from app.services.pro_billing import BillingConfig
from app.services.pro_entitlements import ALLOWED_PRO_FEATURES, ProEntitlementStore, ProProductConfig
from app.storage.pro_accounts import ProAccountStore


client = TestClient(app)


def _admin(monkeypatch, tmp_path):
    path = str(tmp_path / 'pro-routes.db')
    admin = 'a' * 40
    monkeypatch.setenv('MP_DATABASE_PATH', path)
    monkeypatch.setenv('MP_ADMIN_TOKEN', admin)
    return path, {'X-MarketPulse-Admin-Token': admin}


def _issue(monkeypatch, tmp_path):
    path, headers = _admin(monkeypatch, tmp_path)
    response = client.post('/api/v1/admin/pro-accounts', json={'email': 'owner@example.com'}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    return path, body, {'X-PrediBeacon-Pro-Token': body['pro_token']}


def test_pro_account_is_admin_issued_and_private_identity_is_token_derived(monkeypatch, tmp_path):
    path, body, headers = _issue(monkeypatch, tmp_path)
    assert body['account_id'].startswith('acct_')
    assert body['pro_token'].startswith('pp_live_')
    assert client.get('/api/v1/pro/me').status_code == 401

    me = client.get('/api/v1/pro/me?account_id=acct_attacker', headers=headers)
    assert me.status_code == 200
    assert me.json()['account_id'] == body['account_id']
    assert me.json()['billing_customer_bound'] is False
    assert me.headers['cache-control'] == 'no-store'
    assert 'owner@example.com' not in me.text
    assert 'cus_' not in me.text

    stored = ProAccountStore(path).authorize(body['pro_token'])
    assert stored.account_id == body['account_id']


def test_checkout_and_portal_use_authenticated_server_side_account_binding(monkeypatch, tmp_path):
    path, body, headers = _issue(monkeypatch, tmp_path)
    config = BillingConfig('sk_test_x', 'price_test_x', 'whsec_test_x', 'https://predibeacon.com')
    monkeypatch.setattr(routes, '_billing_config', lambda: config)
    calls = {}

    def fake_checkout(**kwargs):
        calls['checkout'] = kwargs
        return SimpleNamespace(url='https://checkout.stripe.com/c/pay/test')

    def fake_portal(**kwargs):
        calls['portal'] = kwargs
        return SimpleNamespace(url='https://billing.stripe.com/p/session/test')

    monkeypatch.setattr(routes, 'create_checkout_session', fake_checkout)
    monkeypatch.setattr(routes, 'create_customer_portal_session', fake_portal)

    checkout = client.post('/api/v1/pro/checkout', headers=headers)
    assert checkout.status_code == 200
    assert calls['checkout']['account_ref'] == body['account_id']
    assert calls['checkout']['customer_email'] == 'owner@example.com'
    assert body['account_id'] not in checkout.text

    ProAccountStore(path).bind_customer(body['account_id'], 'cus_customer123')
    repeat = client.post('/api/v1/pro/checkout', headers=headers)
    assert repeat.status_code == 409
    portal = client.post('/api/v1/pro/portal', headers=headers)
    assert portal.status_code == 200
    assert calls['portal']['stripe_customer_id'] == 'cus_customer123'
    assert 'cus_customer123' not in portal.text


def test_verified_webhook_binds_customer_and_projects_product_entitlement(monkeypatch, tmp_path):
    path, body, headers = _issue(monkeypatch, tmp_path)
    monkeypatch.setenv('MP_PRO_PRODUCT_ID', 'prod_predibeacon_pro')
    monkeypatch.setenv('MP_PRO_BILLING_PROVIDER', 'stripe')
    monkeypatch.setattr(
        routes,
        '_billing_config',
        lambda: BillingConfig('sk_test_x', 'price_test_x', 'whsec_test_x', 'https://predibeacon.com'),
    )

    checkout_event = {
        'id': 'evt_checkout123', 'type': 'checkout.session.completed',
        'data': {'object': {'mode': 'subscription', 'client_reference_id': body['account_id'], 'customer': 'cus_customer123'}},
    }
    monkeypatch.setattr(routes, 'verify_webhook', lambda **kwargs: checkout_event)
    bound = client.post('/api/v1/pro/stripe-webhook', content=b'{}', headers={'Stripe-Signature': 'valid'})
    assert bound.status_code == 200
    assert bound.json()['status'] == 'customer_bound'

    subscription_event = {
        'id': 'evt_subscription123', 'type': 'customer.subscription.updated',
        'data': {'object': {
            'id': 'sub_subscription123', 'customer': 'cus_customer123', 'status': 'active',
            'items': {'data': [{'price': {'product': 'prod_predibeacon_pro'}, 'current_period_end': 1893456000}]},
        }},
    }
    monkeypatch.setattr(routes, 'verify_webhook', lambda **kwargs: subscription_event)
    projected = client.post('/api/v1/pro/stripe-webhook', content=b'{}', headers={'Stripe-Signature': 'valid'})
    assert projected.status_code == 200
    assert projected.json()['status'] == 'entitlement_projected'

    product = ProProductConfig('stripe', 'prod_predibeacon_pro', ALLOWED_PRO_FEATURES)
    assert ProEntitlementStore(path).active_features(body['account_id'], product)
    me = client.get('/api/v1/pro/me', headers=headers)
    assert me.status_code == 200
    assert me.json()['active_features']


def test_webhook_fails_closed_without_product_config_and_unbound_events_retry(monkeypatch, tmp_path):
    path, body, _ = _issue(monkeypatch, tmp_path)
    monkeypatch.setattr(
        routes,
        '_billing_config',
        lambda: BillingConfig('sk_test_x', 'price_test_x', 'whsec_test_x', 'https://predibeacon.com'),
    )
    monkeypatch.delenv('MP_PRO_PRODUCT_ID', raising=False)
    response = client.post('/api/v1/pro/stripe-webhook', content=b'{}', headers={'Stripe-Signature': 'valid'})
    assert response.status_code == 503

    monkeypatch.setenv('MP_PRO_PRODUCT_ID', 'prod_predibeacon_pro')
    event = {
        'id': 'evt_unbound123', 'type': 'customer.subscription.updated',
        'data': {'object': {
            'id': 'sub_subscription123', 'customer': 'cus_unknown123', 'status': 'active',
            'items': {'data': [{'price': {'product': 'prod_predibeacon_pro'}, 'current_period_end': 1893456000}]},
        }},
    }
    monkeypatch.setattr(routes, 'verify_webhook', lambda **kwargs: event)
    retry = client.post('/api/v1/pro/stripe-webhook', content=b'{}', headers={'Stripe-Signature': 'valid'})
    assert retry.status_code == 409
    assert ProAccountStore(path).event_seen('evt_unbound123') is False
