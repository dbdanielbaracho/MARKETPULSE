from fastapi.testclient import TestClient

from app.entrypoint import app


client = TestClient(app)


def test_normal_public_surface_is_sameorigin_framed():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-frame-options"].casefold() == "sameorigin"


def test_embed_surface_keeps_explicit_cross_site_embedding_policy():
    response = client.get("/embed/market")
    assert response.status_code == 200
    assert "x-frame-options" not in response.headers
    assert "frame-ancestors *" in response.headers["content-security-policy"].casefold()
