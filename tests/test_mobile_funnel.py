from fastapi.testclient import TestClient

from app.entrypoint import app
from app.services.mobile_funnel import enhance_mobile_funnel

client = TestClient(app)


def test_home_contains_mobile_first_funnel_and_navigation():
    response = client.get('/')
    assert response.status_code == 200
    body = response.text
    assert 'predibeacon-mobile-funnel-style' in body
    assert 'class="pb-mobile-nav"' in body
    assert 'grid-template-columns:1fr;gap:.55rem' in body
    assert 'min-height:50px' in body
    assert 'href="/#markets">Explore</a>' in body


def test_mobile_funnel_keeps_both_platforms_explicit():
    body = client.get('/').text
    assert 'Kalshi' in body
    assert 'Polymarket' in body
    assert 'data-venue-link="kalshi"' in body
    assert 'data-venue-link="polymarket"' in body


def test_mobile_funnel_is_idempotent():
    source = '<html><head></head><body><main></main></body></html>'
    once = enhance_mobile_funnel(source)
    twice = enhance_mobile_funnel(once)
    assert once == twice
    assert once.count('predibeacon-mobile-funnel-style') == 1
    assert once.count('pb-mobile-nav') == 1
