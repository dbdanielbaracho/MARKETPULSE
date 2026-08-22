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


def test_public_trust_pages_are_available_and_precommercial():
    expected = {
        "/methodology": "AI-assisted content",
        "/risk": "loss of the entire amount",
        "/privacy": "does not currently offer public user accounts",
        "/terms": "No custody or execution",
    }
    for path, marker in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text
        assert response.headers["x-frame-options"] == "DENY"

    home = client.get("/")
    for path in expected:
        assert f'href="{path}"' in home.text


def test_public_base_url_must_be_origin_only_https(monkeypatch):
    import pytest
    import app.main as main

    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "http://example.com/path?unsafe=1")
    with pytest.raises(ValueError):
        main._public_base_url()


def test_www_redirects_to_canonical_origin_without_losing_path_or_query():
    response = client.get(
        "/api/v1/markets?limit=1",
        headers={"host": "www.predibeacon.com"},
        follow_redirects=False,
    )
    assert response.status_code == 308
    assert response.headers["location"] == (
        "https://marketpulse-production-aa9f.up.railway.app/api/v1/markets?limit=1"
    )


def test_non_www_hosts_are_not_redirected():
    response = client.get("/health", headers={"host": "predibeacon.com"}, follow_redirects=False)
    assert response.status_code == 200


def test_home_exposes_explicit_accessible_names_and_touch_targets():
    response = client.get("/")
    for label in (
        "Find a market",
        "Sort markets",
        "Filter by platform",
        "First market to compare",
        "Second market to compare",
    ):
        assert f'aria-label="{label}"' in response.text
    assert "min-height:44px" in response.text
    assert 'aria-atomic="true"' in response.text
