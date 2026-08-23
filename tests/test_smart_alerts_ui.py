from fastapi.testclient import TestClient

from app.entrypoint import app
from app.services.alert_page_enhancements import enhance_alerts_template


client = TestClient(app)


def test_alert_enhancer_adds_observable_signal_alerts():
    source = "<style></style><section class=\"panel\"><h2>Saved alerts</h2><script>document.querySelector('#add').addEventListener('click',add);</script>"
    enhanced = enhance_alerts_template(source)
    assert "Smart signal alerts" in enhanced
    assert "Breaking move" in enhanced
    assert "Weak execution quality" in enhanced
    assert "New large-trade activity" in enhanced
    assert "Verified disagreement ≥ 5 pts" in enhanced
    assert "/api/v1/market/alert-signals?" in enhanced
    assert "Missing data never triggers an alert" in enhanced
    assert "setInterval(checkSmart,300000)" in enhanced


def test_alert_enhancer_fails_closed_if_template_anchors_change():
    source = "<html>unexpected alerts template</html>"
    assert enhance_alerts_template(source) == source


def test_alert_page_exposes_smart_signals_and_preserves_csp():
    response = client.get("/alerts")
    assert response.status_code == 200
    assert "Smart signal alerts" in response.text
    assert "/api/v1/market/alert-signals?" in response.text
    assert "Signal alerts are local browser preferences" in response.text
    assert "not forecasts or trading recommendations" in response.text
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_smart_alerts_trigger_on_transitions_not_missing_data():
    source = client.get("/alerts").text
    assert "snapshot?.breaking?.available&&snapshot.breaking.active" in source
    assert "snapshot?.execution?.available&&snapshot.execution.score!=null" in source
    assert "snapshot?.large_trade_activity?.available?snapshot.large_trade_activity.latest_signal_key:null" in source
    assert "snapshot?.cross_platform?.equivalent_contracts" in source
    assert "next.breaking&&!item.last?.breaking" in source
    assert "next.largeKey&&next.largeKey!==item.last?.largeKey" in source
