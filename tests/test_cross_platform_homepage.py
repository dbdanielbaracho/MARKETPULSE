from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_homepage_cross_platform_scan_is_independent_of_visible_filters():
    page = client.get("/")
    assert page.status_code == 200
    assert "fetchVenueUniverse('kalshi')" in page.text
    assert "fetchVenueUniverse('polymarket')" in page.text
    assert "complete current discovery set" in page.text
    assert "renderComparisons(data)" not in page.text


def test_homepage_fails_closed_on_unverified_cross_platform_contracts():
    page = client.get("/")
    assert page.status_code == 200
    assert "cannot yet verify identical resolution rules" in page.text
    assert "Not labeled equivalent" in page.text
    assert "Verified equivalent contracts" in page.text


def test_cross_platform_scan_refreshes_without_user_search():
    page = client.get("/")
    assert page.status_code == 200
    assert "setInterval(renderComparisons,300000)" in page.text
