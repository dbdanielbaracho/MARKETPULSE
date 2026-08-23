from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_top_route_is_predibeacon_intelligence_dashboard():
    page = client.get('/top')
    assert page.status_code == 200
    assert 'PREDIBEACON INTELLIGENCE' in page.text
    assert 'SMART MOVERS' in page.text
    assert 'HIGH ATTENTION' in page.text
    assert 'VERIFIED CROSS-PLATFORM' in page.text
    assert 'Attention scores measure market signal strength' in page.text


def test_intelligence_never_calls_unverified_pairs_opportunities():
    page = client.get('/top')
    assert page.status_code == 200
    assert 'Only pairs that pass the equivalence gate are ranked' in page.text
    assert 'VERIFIED EQUIVALENT' in page.text
    assert 'arbitrage opportunity' not in page.text.lower()
