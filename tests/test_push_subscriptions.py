import sqlite3

import pytest

from app.storage.push_subscriptions import PushSubscriptionStore


VALID_ENDPOINT = 'https://fcm.googleapis.com/fcm/send/test-subscription'
P256DH = 'A' * 88
AUTH = 'B' * 24
TOKEN = 'pb_push_' + 'x' * 48


def _created_store(tmp_path):
    path = str(tmp_path / 'push.db')
    store = PushSubscriptionStore(path)
    created = store.create(
        subscription_id='push_test_12345678',
        endpoint=VALID_ENDPOINT,
        p256dh=P256DH,
        auth=AUTH,
        raw_token=TOKEN,
    )
    return path, store, created


def test_push_management_token_is_hashed_at_rest_and_revocable(tmp_path):
    path, store, created = _created_store(tmp_path)
    assert created.endpoint == VALID_ENDPOINT
    assert store.authorize(created.subscription_id, TOKEN).active is True
    with pytest.raises(PermissionError):
        store.authorize(created.subscription_id, TOKEN + 'wrong')

    with sqlite3.connect(path) as connection:
        token_hash, endpoint = connection.execute(
            'SELECT token_hash, endpoint FROM push_subscriptions WHERE subscription_id=?',
            (created.subscription_id,),
        ).fetchone()
    assert token_hash != TOKEN
    assert TOKEN not in token_hash
    assert endpoint == VALID_ENDPOINT

    store.upsert_alert(
        subscription_id=created.subscription_id,
        market_id='kalshi:test-market',
        preferences={'breaking': True, 'closing_hours': 24},
        last_state={'breaking': False, 'closing_hours': 48},
    )
    alerts = store.active_alerts()
    assert len(alerts) == 1
    assert alerts[0].preferences['breaking'] is True

    assert store.revoke(created.subscription_id) is True
    assert store.active_alerts() == []
    with pytest.raises(PermissionError):
        store.authorize(created.subscription_id, TOKEN)


def test_replace_alerts_atomically_deactivates_removed_markets(tmp_path):
    _, store, created = _created_store(tmp_path)
    store.replace_alerts(
        subscription_id=created.subscription_id,
        alerts=[
            ('kalshi:one', {'breaking': True}, {'breaking': False}),
            ('polymarket:two', {'evidence': True}, {'evidence_key': 'old'}),
        ],
    )
    assert {item.market_id for item in store.active_alerts()} == {'kalshi:one', 'polymarket:two'}

    store.replace_alerts(
        subscription_id=created.subscription_id,
        alerts=[('kalshi:one', {'breaking': False}, {'breaking': False})],
    )
    active = store.active_alerts()
    assert [item.market_id for item in active] == ['kalshi:one']
    assert active[0].preferences['breaking'] is False


def test_replace_alerts_validation_failure_preserves_previous_active_set(tmp_path):
    _, store, created = _created_store(tmp_path)
    store.replace_alerts(
        subscription_id=created.subscription_id,
        alerts=[('kalshi:one', {'breaking': True}, {'breaking': False})],
    )
    with pytest.raises(ValueError):
        store.replace_alerts(
            subscription_id=created.subscription_id,
            alerts=[('not valid market id!', {'breaking': False}, {'breaking': False})],
        )
    active = store.active_alerts()
    assert [item.market_id for item in active] == ['kalshi:one']
    assert active[0].preferences['breaking'] is True


def test_push_endpoint_is_allowlisted_to_browser_push_services(tmp_path):
    store = PushSubscriptionStore(str(tmp_path / 'push.db'))
    for endpoint in (
        'http://fcm.googleapis.com/fcm/send/x',
        'https://example.com/push',
        'https://127.0.0.1/push',
        'https://localhost/push',
    ):
        with pytest.raises(ValueError, match='allowlisted'):
            store.create(
                subscription_id='push_test_12345678',
                endpoint=endpoint,
                p256dh=P256DH,
                auth=AUTH,
                raw_token=TOKEN,
            )


def test_push_keys_and_alert_payloads_are_bounded(tmp_path):
    store = PushSubscriptionStore(str(tmp_path / 'push.db'))
    with pytest.raises(ValueError):
        store.create(
            subscription_id='push_test_12345678',
            endpoint=VALID_ENDPOINT,
            p256dh='short',
            auth=AUTH,
            raw_token=TOKEN,
        )
