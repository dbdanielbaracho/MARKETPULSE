from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_is_deterministic():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "marketpulse-web"


def test_status_exposes_country_and_version():
    response = client.get("/api/v1/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["country"] == "US"
    assert payload["version"]
    assert payload["freshness"] in {"fresh", "stale", "future", "unavailable"}
    assert payload["stale_after_seconds"] >= 60


def test_home_has_accessible_discovery_controls():
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="#main"' in response.text
    assert 'type="search"' in response.text
    assert 'aria-live="polite"' in response.text
    assert 'data-evidence-id' in response.text


def test_seo_endpoints_and_canonical_are_consistent():
    home = client.get("/")
    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")

    assert home.status_code == 200
    assert 'rel="canonical"' in home.text
    assert 'application/ld+json' in home.text
    assert 'property="og:url"' in home.text
    assert "PREDIBEACON" in home.text
    assert "PrediBeacon — Prediction market intelligence" in home.text
    assert '"name":"PrediBeacon"' in home.text
    assert "MarketPulse helps" not in home.text
    assert robots.status_code == 200
    assert robots.text.splitlines() == [
        "User-agent: *",
        "Allow: /",
        "Sitemap: https://marketpulse-production-aa9f.up.railway.app/sitemap.xml",
    ]
    assert r"\\n" not in robots.text
    assert sitemap.status_code == 200
    assert "<loc>https://marketpulse-production-aa9f.up.railway.app/</loc>" in sitemap.text


def test_public_base_url_must_be_origin_only_https(monkeypatch):
    import pytest
    import app.main as main

    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "http://example.com/path?unsafe=1")
    with pytest.raises(ValueError):
        main._public_base_url()
