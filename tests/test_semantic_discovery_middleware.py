from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from app.middleware.semantic_discovery import register_semantic_discovery_middleware
from app.services.discovery_semantics import SEMANTIC_DISCOVERY_VERSION


def _app(path: str = "/") -> FastAPI:
    api = FastAPI()

    @api.get(path)
    def page():
        return HTMLResponse(
            '<html lang="pt-BR"><body><p id="count">0 mercados</p>'
            '<div id="state">No markets match these filters.</div>'
            '<script>fetch("/api/v1/markets?sort=trending");'
            'const visible=Math.round(m.trend_score);</script></body></html>'
        )

    register_semantic_discovery_middleware(api)
    return api


def test_home_consumes_dedicated_discovery_contract_and_localized_runtime_copy():
    response = TestClient(_app()).get("/")
    assert response.status_code == 200
    assert response.headers["x-predibeacon-semantic-discovery"] == SEMANTIC_DISCOVERY_VERSION
    assert "/api/v1/discovery?sort=trending" in response.text
    assert "/api/v1/markets?sort=trending" not in response.text
    assert "Math.round(m.relevance_score??m.trend_score)" in response.text
    assert "Math.round(m.trend_score)" not in response.text
    assert 'data-predibeacon-semantic-discovery="semantic-discovery-v1"' in response.text
    assert "Nenhum mercado atende agora aos critérios documentados de atenção" in response.text
    assert "window.why = function(m)" in response.text


def test_top_consumes_same_semantic_discovery_contract():
    response = TestClient(_app("/top")).get("/top")
    assert response.status_code == 200
    assert response.headers["x-predibeacon-semantic-discovery"] == SEMANTIC_DISCOVERY_VERSION
    assert "/api/v1/discovery?sort=trending" in response.text
    assert "Math.round(m.relevance_score??m.trend_score)" in response.text


def test_non_discovery_surface_is_not_rewritten():
    api = FastAPI()

    @api.get("/other")
    def other():
        return HTMLResponse('<script>fetch("/api/v1/markets?sort=trending");const visible=Math.round(m.trend_score);</script>')

    register_semantic_discovery_middleware(api)
    response = TestClient(api).get("/other")
    assert "/api/v1/markets?sort=trending" in response.text
    assert "Math.round(m.trend_score)" in response.text
    assert "x-predibeacon-semantic-discovery" not in response.headers
