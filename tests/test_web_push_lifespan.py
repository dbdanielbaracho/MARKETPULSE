import asyncio
from types import SimpleNamespace

import app.routes.web_push as push_routes


def test_push_lifespan_does_not_start_dispatcher_when_vapid_is_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(push_routes, 'web_push_config', lambda: SimpleNamespace(enabled=False))

    async def fake_dispatch(store):
        calls.append(store)

    monkeypatch.setattr(push_routes, 'dispatch_push_alerts_once', fake_dispatch)

    async def scenario():
        async with push_routes._lifespan(None):
            await asyncio.sleep(0)

    asyncio.run(scenario())
    assert calls == []


def test_push_lifespan_starts_dispatcher_and_stops_cleanly_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(push_routes, 'web_push_config', lambda: SimpleNamespace(enabled=True))
    monkeypatch.setattr(push_routes, '_store', lambda: 'store')

    async def fake_dispatch(store):
        calls.append(store)

    monkeypatch.setattr(push_routes, 'dispatch_push_alerts_once', fake_dispatch)

    async def scenario():
        async with push_routes._lifespan(None):
            for _ in range(20):
                if calls:
                    break
                await asyncio.sleep(0)

    asyncio.run(scenario())
    assert calls == ['store']
