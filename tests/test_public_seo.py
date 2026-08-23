from fastapi.testclient import TestClient

from app.entrypoint import app
from app.middleware.public_seo import _public_base_url


client = TestClient(app)


def test_home_uses_public_domain_for_canonical_and_social_metadata(monkeypatch):
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    response = client.get("/?venue=kalshi")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://predibeacon.com/">' in response.text
    assert '<meta property="og:site_name" content="PrediBeacon">' in response.text
    assert '<meta property="og:url" content="https://predibeacon.com/">' in response.text
    assert '<meta name="twitter:card" content="summary">' in response.text


def test_public_static_page_gets_path_canonical(monkeypatch):
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    response = client.get("/methodology")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://predibeacon.com/methodology">' in response.text


def test_seo_helper_fails_closed_to_predibeacon(monkeypatch):
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "http://invalid.example")
    assert _public_base_url() == "https://predibeacon.com"


def test_admin_and_legacy_query_market_are_not_canonicalized(monkeypatch):
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    admin = client.get("/admin")
    legacy = client.get("/market?market_id=missing")
    assert 'rel="canonical"' not in admin.text
    assert 'rel="canonical"' not in legacy.text
