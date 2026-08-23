from fastapi.testclient import TestClient

from app.entrypoint import app


client = TestClient(app)


def test_localized_html_sets_content_language_and_vary_cookie():
    page = client.get('/', cookies={'predibeacon_lang': 'de'})
    assert page.status_code == 200
    assert page.headers['content-language'] == 'de'
    assert 'Cookie' in page.headers['vary']
