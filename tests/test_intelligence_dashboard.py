from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_top_route_is_predibeacon_intelligence_dashboard():
    page = client.get('/top')
    assert page.status_code == 200
    assert 'PREDIBEACON INTELLIGENCE' in page.text
    assert 'Smart movers' in page.text
    assert 'BREAKING MARKETS' in page.text
    assert 'MARKET QUALITY' in page.text
    assert 'VERIFIED CONSENSUS' in page.text
    assert 'Attention and Quality scores describe the strength and completeness' in page.text


def test_intelligence_never_calls_unverified_pairs_opportunities():
    page = client.get('/top')
    assert page.status_code == 200
    assert 'contract-equivalence gate passes' in page.text
    assert 'VERIFIED EQUIVALENT' in page.text
    assert 'arbitrage opportunity' not in page.text.lower()
