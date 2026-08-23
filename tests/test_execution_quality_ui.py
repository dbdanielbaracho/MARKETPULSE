from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
from app.entrypoint import app
from app.services.market_page_enhancements import enhance_market_template


client = TestClient(app)


def test_market_template_enhancer_adds_execution_panel_and_safe_language():
    source = (
        '<section class="panel"><div class="eyebrow">CROSS-PLATFORM CHECK</div>'
        '<script>async function loadSignals(){}loadMarket();loadSignals();</script>'
    )
    enhanced = enhance_market_template(source)
    assert "EXECUTION QUALITY" in enhanced
    assert "/api/v1/market/execution-quality?" in enhanced
    assert "Best bid" in enhanced
    assert "Best ask" in enhanced
    assert "Spread" in enhanced
    assert "best-execution guarantee" in enhanced
    assert "setInterval(loadExecutionQuality,30000)" in enhanced


def test_market_template_enhancer_fails_closed_if_template_anchors_change():
    source = "<html><body>unexpected template</body></html>"
    assert enhance_market_template(source) == source


def test_market_page_exposes_execution_quality_without_weakening_csp():
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id="kalshi:KXUI",
            title="Will X happen?",
            venue="kalshi",
            probability=.55,
            trend_score=70,
            observed_at=datetime.now(timezone.utc),
        )
    ])
    response = client.get("/market", params={"market_id": "kalshi:KXUI"})
    assert response.status_code == 200
    assert "EXECUTION QUALITY" in response.text
    assert "/api/v1/market/execution-quality?" in response.text
    assert "currently displayed order book" in response.text
    assert "best-execution guarantee" in response.text
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_non_market_page_is_not_modified_by_execution_ui_middleware():
    response = client.get("/top")
    assert response.status_code == 200
    assert "EXECUTION QUALITY" not in response.text
