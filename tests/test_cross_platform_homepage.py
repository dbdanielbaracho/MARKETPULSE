from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_homepage_cross_platform_scan_is_independent_of_visible_filters():
    page = client.get("/")
    assert page.status_code == 200
    assert "/api/v1/compare/pairs?" in page.text
    assert "checks both current provider feeds" in page.text
    assert "candidate_limit" in page.text


def test_homepage_fails_closed_on_unverified_cross_platform_contracts():
    page = client.get("/")
    assert page.status_code == 200
    assert "equivalence is not verified" in page.text
    assert "Not ranked as a disagreement" in page.text
    assert "VERIFIED" in page.text
    assert "Only verified equivalent contracts enter this ranking" in page.text
    assert "equivalent_contracts" in page.text


def test_cross_platform_scan_refreshes_without_user_search():
    page = client.get("/")
    assert page.status_code == 200
    assert "setInterval(()=>{status();comparisons()},300000)" in page.text
    assert 'id="search"' not in page.text
