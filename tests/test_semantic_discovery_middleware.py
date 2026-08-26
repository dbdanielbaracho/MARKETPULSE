from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from app.middleware.semantic_discovery import register_semantic_discovery_middleware
from app.services.discovery_semantics import SEMANTIC_DISCOVERY_VERSION

NOW = datetime.now(timezone.utc)


def item(title: str, volume: float, trend: float, move: float = 0.04):
    return {
        "canonical_id": f"kalshi:{title}",
        "title": title,
        "venue": "kalshi",
        "probability": 0.5,
        "probability_change": move,
        "volume_usd": volume,
        "trend_score": trend,
        "observed_at": NOW.isoformat(),
        "closes_at": (NOW + timedelta(days=2)).isoformat(),
        "source_url": "https://kalshi.com/markets/example",
    }


def test_api_semantic_gate_filters_valid_but_weak_inventory_and_exposes_oracle_fields():
    api = FastAPI()

    @api.get("/api/v1/markets")
    def markets():
        return [
            item("Material", 20_800.0, 37.0),
            item("Washington thin escape", 149.0, 13.0, 0.105),
            item("Byron thin escape", 302.0, 11.0, -0.02),
        ]

    register_semantic_discovery_middleware(api)
    response = TestClient(api).get("/api/v1/markets")

    assert response.status_code == 200
    assert response.headers["x-predibeacon-semantic-discovery"] == SEMANTIC_DISCOVERY_VERSION
    assert response.headers["x-predibeacon-semantic-input-count"] == "3"
    assert response.headers["x-predibeacon-semantic-output-count"] == "1"
    payload = response.json()
    assert [row["title"] for row in payload] == ["Material"]
    assert payload[0]["volume_usd"] >= 1000
    assert payload[0]["relevance_score"] >= 20
    assert payload[0]["attention_reason_code"]


def test_api_semantic_gate_returns_truthful_empty_set_instead_of_weak_fallback():
    api = FastAPI()

    @api.get("/api/v1/markets")
    def markets():
        return [item("Thin A", 149.0, 90.0), item("Thin B", 302.0, 80.0)]

    register_semantic_discovery_middleware(api)
    response = TestClient(api).get("/api/v1/markets")

    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["x-predibeacon-semantic-input-count"] == "2"
    assert response.headers["x-predibeacon-semantic-output-count"] == "0"


def test_home_receives_semantic_explanation_and_localized_empty_state_runtime():
    api = FastAPI()

    @api.get("/")
    def home():
        return HTMLResponse('<html lang="pt-BR"><body><p id="count">0 mercados</p><div id="state">No markets match these filters.</div></body></html>')

    register_semantic_discovery_middleware(api)
    response = TestClient(api).get("/")

    assert response.status_code == 200
    assert 'data-predibeacon-semantic-discovery="semantic-discovery-v1"' in response.text
    assert "Nenhum mercado atende agora aos critérios documentados de atenção" in response.text
    assert "window.why = function(m)" in response.text
