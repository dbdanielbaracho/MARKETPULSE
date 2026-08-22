from concurrent.futures import ThreadPoolExecutor

from app.storage.api_keys import ApiKeyStore


def test_wal_serializes_concurrent_quota_writes_without_lost_updates(tmp_path):
    store = ApiKeyStore(str(tmp_path / "concurrency.db"))
    token = "pb_live_" + "z" * 40
    store.create(
        key_id="concurrent",
        raw_token=token,
        name="Concurrency client",
        plan="business",
        scopes=("markets:read",),
        daily_limit=200,
    )

    with ThreadPoolExecutor(max_workers=12) as pool:
        principals = list(pool.map(lambda _: store.authorize(token, "markets:read"), range(60)))

    assert sorted(item.usage_today for item in principals) == list(range(1, 61))
    assert store.authorize(token, "markets:read").usage_today == 61
