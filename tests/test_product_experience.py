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
    assert "Escolher mercado" in page.text
    assert "Criar alerta" in page.text
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
    assert "SINAL ATUAL DO MERCADO" in page.text
    assert "POR QUE IMPORTA" in page.text
    assert "Tempo restante" in page.text
    assert "Última observação" in page.text
    assert "Criar alerta" in page.text
    assert "Relacionado não significa equivalente" in page.text
