from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_homepage_has_no_low_value_market_search_box():
    page = client.get("/")
    assert page.status_code == 200
    assert "FIND A MARKET" not in page.text
    assert 'id="search"' not in page.text
    assert "Biggest verified disagreements" in page.text


def test_alerts_do_not_ask_customers_for_market_ids():
    page = client.get("/alerts")
    assert page.status_code == 200
    assert 'id="market-id"' not in page.text
    assert "Choose market" in page.text
    assert "Create alert" in page.text
    assert "predibeacon-watchlist" in page.text


def test_watchlist_is_an_actionable_intelligence_view():
    page = client.get("/watchlist")
    assert page.status_code == 200
    assert "YOUR INTELLIGENCE" in page.text
    assert "Reported volume" in page.text
    assert "Create alert" in page.text
    assert "PrediBeacon does not silently replace it" in page.text


def test_market_detail_explains_attention_and_next_actions():
    page = client.get("/market")
    assert page.status_code == 200
    assert "CURRENT MARKET SIGNAL" in page.text
    assert "WHY IT MATTERS" in page.text
    assert "Time remaining" in page.text
    assert "Last observed" in page.text
    assert "Create alert" in page.text
    assert "Related does not mean equivalent" in page.text
