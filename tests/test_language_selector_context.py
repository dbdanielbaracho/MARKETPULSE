from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.main import DiscoveryMarket, set_discovery_markets


client = TestClient(app)


def test_market_language_selector_preserves_market_id_query():
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id='kalshi:keep-context',
            title='Keep context market',
            venue='kalshi',
            probability=.5,
            trend_score=50,
            observed_at=datetime.now(timezone.utc),
        )
    ])
    page = client.get('/market', params={'market_id': 'kalshi:keep-context'})
    assert page.status_code == 200
    assert '/set-language?lang=es&next=/market?market_id=kalshi%3Akeep-context' in page.text
    assert '/set-language?lang=pt-BR&next=/market?market_id=kalshi%3Akeep-context' in page.text


def test_alert_language_selector_preserves_selected_market_query():
    page = client.get('/alerts', params={'market_id': 'kalshi:keep-context'})
    assert page.status_code == 200
    assert '/set-language?lang=es&next=/alerts?market_id=kalshi%3Akeep-context' in page.text
