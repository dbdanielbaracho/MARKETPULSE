from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.entrypoint import app


ROOT = Path(__file__).parents[1]
client = TestClient(app)


def test_home_injects_attributable_card_exit_without_raw_provider_destination():
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert 'id="predibeacon-home-card-outbound"' in body
    assert "`/out/${venue}?${new URLSearchParams({market_id:id,channel:'home_card'})}`" in body
    assert "window.open(outbound,'_blank','noopener,noreferrer')" in body
    assert "event.target.closest('a,button,input,select,textarea,label')" in body
    injected = body.split('id="predibeacon-home-card-outbound"', 1)[1]
    assert "https://kalshi.com" not in injected
    assert "https://www.kalshi.com" not in injected
    assert "https://polymarket.com" not in injected
    assert "https://www.polymarket.com" not in injected


def test_non_home_pages_do_not_receive_home_card_exit_script():
    response = client.get("/health")

    assert response.status_code == 200
    assert 'predibeacon-home-card-outbound' not in response.text


def test_public_ui_sources_do_not_hardcode_direct_kalshi_or_polymarket_links():
    direct_link = re.compile(
        r"(?:href\s*=\s*[\"']|window\.open\(\s*[\"'])https://(?:www\.)?(?:kalshi|polymarket)\.com",
        re.IGNORECASE,
    )
    offenders: list[str] = []
    for directory in (ROOT / "app" / "templates", ROOT / "app" / "static", ROOT / "app" / "middleware"):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.suffix not in {".html", ".js", ".py"}:
                continue
            if direct_link.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == [], f"provider exits must route through PrediBeacon attribution: {offenders}"
