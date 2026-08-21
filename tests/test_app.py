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


def test_home_has_accessible_discovery_controls():
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="#main"' in response.text
    assert 'type="search"' in response.text
    assert 'aria-live="polite"' in response.text
