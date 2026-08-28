import asyncio

from app.services import kalshi_category_pool as pool_module
from app.services.kalshi_category_pool import fetch_kalshi_category_pool


class _Response:
    def __init__(self, payload, *, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request('GET', 'https://example.test')
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError('error', request=request, response=response)
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self):
        self.calls = []
        self.series_429_remaining = 0
        self.fail_tech_events = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params=None):
        params = params or {}
        self.calls.append((url, params))
        if url.endswith('/series') and self.series_429_remaining:
            self.series_429_remaining -= 1
            return _Response({}, status_code=429, headers={'retry-after': '0'})
        if url.endswith('/series'):
            return _Response({
                'series': [
                    {'ticker': 'POL1', 'category': 'Politics', 'volume_fp': '100000'},
                    {'ticker': 'TECH1', 'category': 'Science and Technology', 'volume_fp': '90000'},
                    {'ticker': 'SPORT1', 'category': 'Sports', 'volume_fp': '9999999'},
                ]
            })
        if url.endswith('/events') and params.get('series_ticker') == 'POL1':
            return _Response({'events': [{
                'event_ticker': 'POL1-EVENT',
                'series_ticker': 'POL1',
                'markets': [{
                    'ticker': 'POL1-MKT',
                    'title': 'Will outcome A happen?',
                    'volume_fp': '5000',
                    'volume_24h_fp': '2400',
                }],
            }]})
        if url.endswith('/events') and params.get('series_ticker') == 'TECH1':
            if self.fail_tech_events:
                return _Response({}, status_code=503)
            return _Response({'events': [{
                'event_ticker': 'TECH1-EVENT',
                'series_ticker': 'TECH1',
                'markets': [{
                    'ticker': 'TECH1-MKT',
                    'title': 'Will outcome B happen?',
                    'volume_fp': '8000',
                    'volume_24h_fp': '4200',
                }],
            }]})
        return _Response({'events': []})


class _PaginatedClient(_Client):
    async def get(self, url, params=None):
        params = params or {}
        if url.endswith('/events') and params.get('series_ticker') == 'POL1':
            self.calls.append((url, params))
            if not params.get('cursor'):
                return _Response({
                    'events': [{
                        'event_ticker': 'POL1-FIRST',
                        'markets': [{'ticker': 'POL1-LOW', 'title': 'First page', 'volume_fp': '1000', 'volume_24h_fp': '100'}],
                    }],
                    'cursor': 'next-page',
                })
            return _Response({
                'events': [{
                    'event_ticker': 'POL1-SECOND',
                    'markets': [{'ticker': 'POL1-HIGH', 'title': 'Second page', 'volume_fp': '9000', 'volume_24h_fp': '5000'}],
                }]
            })
        return await super().get(url, params)


def _reset_cache():
    pool_module._CACHE.clear()


def test_category_pool_discovers_politics_and_science_technology_from_provider_metadata(monkeypatch):
    _reset_cache()
    client = _Client()
    monkeypatch.setattr('app.services.kalshi_category_pool.httpx.AsyncClient', lambda **kwargs: client)
    markets = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100,
    ))
    assert [market.venue_market_id for market in markets] == ['TECH1-MKT', 'POL1-MKT']
    assert {market.category for market in markets} == {'Politics', 'Tech'}
    assert all(market.source_url is not None for market in markets)
    series_calls = [call for call in client.calls if call[0].endswith('/series')]
    event_calls = [call for call in client.calls if call[0].endswith('/events')]
    assert len(series_calls) == 1
    assert {params['series_ticker'] for _, params in event_calls} == {'POL1', 'TECH1'}
    assert all(params['status'] == 'open' for _, params in event_calls)
    assert all(params['with_nested_markets'] == 'true' for _, params in event_calls)


def test_category_pool_follows_event_cursor_before_ranking(monkeypatch):
    _reset_cache()
    client = _PaginatedClient()
    monkeypatch.setattr('app.services.kalshi_category_pool.httpx.AsyncClient', lambda **kwargs: client)
    markets = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics',),
        now_monotonic=100,
    ))
    assert [market.venue_market_id for market in markets] == ['POL1-HIGH', 'POL1-LOW']
    politics_event_calls = [params for url, params in client.calls if url.endswith('/events') and params.get('series_ticker') == 'POL1']
    assert len(politics_event_calls) == 2
    assert politics_event_calls[1]['cursor'] == 'next-page'


def test_category_pool_does_not_treat_sports_as_target_when_not_requested(monkeypatch):
    _reset_cache()
    client = _Client()
    monkeypatch.setattr('app.services.kalshi_category_pool.httpx.AsyncClient', lambda **kwargs: client)
    asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100,
    ))
    assert not any(params.get('series_ticker') == 'SPORT1' for _, params in client.calls)


def test_category_pool_cache_avoids_provider_calls_on_every_refresh(monkeypatch):
    _reset_cache()
    client = _Client()
    monkeypatch.setattr('app.services.kalshi_category_pool.httpx.AsyncClient', lambda **kwargs: client)
    first = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100,
    ))
    call_count = len(client.calls)
    second = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100 + pool_module.CATEGORY_POOL_TTL_SECONDS - 1,
    ))
    assert [m.canonical_id for m in first] == [m.canonical_id for m in second]
    assert len(client.calls) == call_count


def test_category_pool_retries_429_without_losing_category_coverage(monkeypatch):
    _reset_cache()
    client = _Client()
    client.series_429_remaining = 1
    monkeypatch.setattr('app.services.kalshi_category_pool.httpx.AsyncClient', lambda **kwargs: client)
    markets = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100,
    ))
    series_calls = [call for call in client.calls if call[0].endswith('/series')]
    assert len(series_calls) == 2
    assert {market.category for market in markets} == {'Politics', 'Tech'}


def test_partial_refresh_keeps_last_complete_cached_pool(monkeypatch):
    _reset_cache()
    client = _Client()
    monkeypatch.setattr('app.services.kalshi_category_pool.httpx.AsyncClient', lambda **kwargs: client)
    first = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100,
    ))
    client.fail_tech_events = True
    second = asyncio.run(fetch_kalshi_category_pool(
        base_url='https://external-api.kalshi.com/trade-api/v2',
        categories=('Politics', 'Science and Technology'),
        now_monotonic=100 + pool_module.CATEGORY_POOL_TTL_SECONDS + 1,
    ))
    assert [m.canonical_id for m in second] == [m.canonical_id for m in first]
    assert {market.category for market in second} == {'Politics', 'Tech'}
