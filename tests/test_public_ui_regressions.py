from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_empty_briefs_page_uses_predibeacon_design(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "briefs.db"))
    response = client.get("/articles")

    assert response.status_code == 200
    assert "PREDIBEACON BRIEFS" in response.text
    assert "NO BRIEFS PUBLISHED YET" in response.text
    assert "This is not a data error" in response.text
    assert "Explore live markets" in response.text
    assert "--accent:#8be9c7" in response.text
    assert "__ARTICLE_CONTENT__" not in response.text


def test_homepage_exposes_verified_disagreement_intelligence():
    response = client.get("/")

    assert response.status_code == 200
    assert "Biggest verified disagreements" in response.text
    assert "Unverified lookalikes are excluded" in response.text
    assert "function gap(" in response.text
    assert "/api/v1/compare/pairs?" in response.text
    assert "equivalent_contracts" in response.text
    assert "Not ranked as a disagreement" in response.text
