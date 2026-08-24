from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routes.web_push as push_routes
from app.entrypoint import app
from app.storage.push_subscriptions import PushSubscriptionStore


client = TestClient(app)


def _configure_vapid(monkeypatch):
    monkeypatch.setenv('MP_WEB_PUSH_VAPID_PUBLIC_KEY', 'A' * 64)
    monkeypatch.setenv('MP_WEB_PUSH_VAPID_PRIVATE_KEY', 'private-' + 'x' * 40)
    monkeypatch.setenv('MP_WEB_PUSH_VAPID_SUBJECT', 'mailto:ops@predibeacon.com')


def test_push_config_is_fail_closed_without_vapid(monkeypatch):
    for key in ('MP_WEB_PUSH_VAPID_PUBLIC_KEY', 'MP_WEB_PUSH_VAPID_PRIVATE_KEY', 'MP_WEB_PUSH_VAPID_SUBJECT'):
        monkeypatch.delenv(key, raising=False)
    response = client.get('/api/v1/push/config')
    assert response.status_code == 200
    assert response.json() == {'enabled': False, 'public_key': None, 'reason': 'vapid_not_configured'}
    assert response.headers['cache-control'] == 'no-store'


def test_subscription_creation_requires_vapid(monkeypatch, tmp_path):
    for key in ('MP_WEB_PUSH_VAPID_PUBLIC_KEY', 'MP_WEB_PUSH_VAPID_PRIVATE_KEY', 'MP_WEB_PUSH_VAPID_SUBJECT'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('MP_DATABASE_PATH', str(tmp_path / 'push.db'))
    response = client.post('/api/v1/push/subscriptions', json={
        'endpoint': 'https://fcm.googleapis.com/fcm/send/test',
        'keys': {'p256dh': 'A' * 88, 'auth': 'B' * 24},
        'alerts': [{'market_id': 'kalshi:test'}],
    })
    assert response.status_code == 503


def test_subscription_token_is_returned_once_and_authorizes_atomic_replacement(monkeypatch, tmp_path):
    _configure_vapid(monkeypatch)
    database_path = str(tmp_path / 'push.db')
    monkeypatch.setenv('MP_DATABASE_PATH', database_path)

    async def fake_snapshot(response, market_id):
        return SimpleNamespace(market_id=market_id)

    monkeypatch.setattr(push_routes, 'market_alert_signals', fake_snapshot)
    monkeypatch.setattr(push_routes, 'alert_state', lambda snapshot: {
        'probability': 0.5,
        'breaking': False,
        'execution': False,
        'large_key': None,
        'gap': False,
        'evidence_key': None,
        'closing_hours': 72,
    })

    payload = {
        'endpoint': 'https://fcm.googleapis.com/fcm/send/test',
        'keys': {'p256dh': 'A' * 88, 'auth': 'B' * 24},
        'alerts': [
            {'market_id': 'kalshi:test', 'probability_threshold': 0.7},
            {'market_id': 'polymarket:remove-me', 'evidence': True},
        ],
    }
    created = client.post('/api/v1/push/subscriptions', json=payload)
    assert created.status_code == 200
    body = created.json()
    assert body['management_token'].startswith('pb_push_')
    assert 'p256dh' not in created.text
    assert 'fcm.googleapis.com' not in created.text
    headers = {'X-PrediBeacon-Push-Token': body['management_token']}
    assert {item.market_id for item in PushSubscriptionStore(database_path).active_alerts()} == {
        'kalshi:test', 'polymarket:remove-me'
    }

    updated = client.put(
        f"/api/v1/push/subscriptions/{body['subscription_id']}/alerts",
        headers=headers,
        json={'alerts': [{'market_id': 'kalshi:test', 'breaking': True}]},
    )
    assert updated.status_code == 200
    assert updated.json()['alert_count'] == 1
    active = PushSubscriptionStore(database_path).active_alerts()
    assert [item.market_id for item in active] == ['kalshi:test']

    denied = client.put(
        f"/api/v1/push/subscriptions/{body['subscription_id']}/alerts",
        headers={'X-PrediBeacon-Push-Token': 'wrong'},
        json={'alerts': [{'market_id': 'kalshi:test', 'breaking': True}]},
    )
    assert denied.status_code == 401

    revoked = client.delete(
        f"/api/v1/push/subscriptions/{body['subscription_id']}",
        headers=headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()['active'] is False
