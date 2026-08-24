import sqlite3

import pytest

from app.storage.pro_accounts import ProAccountStore


TOKEN = 'pp_live_' + 'x' * 48
ACCOUNT = 'acct_' + 'a' * 32


def test_pro_token_is_hashed_at_rest_and_customer_binding_is_one_to_one(tmp_path):
    path = str(tmp_path / 'pro-accounts.db')
    store = ProAccountStore(path)
    account = store.create(account_id=ACCOUNT, email='Owner@Example.com', raw_token=TOKEN)
    assert account.email == 'owner@example.com'
    assert store.authorize(TOKEN).account_id == ACCOUNT

    with sqlite3.connect(path) as connection:
        stored = connection.execute(
            'SELECT token_hash,stripe_customer_id FROM pro_accounts WHERE account_id=?', (ACCOUNT,)
        ).fetchone()
    assert TOKEN not in stored[0]
    assert len(stored[0]) == 64
    assert stored[1] is None

    bound = store.bind_customer(ACCOUNT, 'cus_customer123')
    assert bound.stripe_customer_id == 'cus_customer123'
    assert store.by_customer('cus_customer123').account_id == ACCOUNT
    assert store.bind_customer(ACCOUNT, 'cus_customer123').account_id == ACCOUNT
    with pytest.raises(ValueError, match='different customer'):
        store.bind_customer(ACCOUNT, 'cus_other123')

    second = 'acct_' + 'b' * 32
    store.create(account_id=second, email='second@example.com', raw_token='pp_live_' + 'y' * 48)
    with pytest.raises(ValueError, match='another Pro account'):
        store.bind_customer(second, 'cus_customer123')


def test_pro_account_revocation_is_immediate(tmp_path):
    store = ProAccountStore(str(tmp_path / 'pro-revoke.db'))
    store.create(account_id=ACCOUNT, email='owner@example.com', raw_token=TOKEN)
    assert store.revoke(ACCOUNT) is True
    with pytest.raises(PermissionError):
        store.authorize(TOKEN)
    assert store.revoke(ACCOUNT) is False


def test_billing_event_ids_are_recorded_only_once(tmp_path):
    store = ProAccountStore(str(tmp_path / 'events.db'))
    assert store.event_seen('evt_event123') is False
    assert store.mark_event_once('evt_event123', 'customer.subscription.updated') is True
    assert store.event_seen('evt_event123') is True
    assert store.mark_event_once('evt_event123', 'customer.subscription.updated') is False
