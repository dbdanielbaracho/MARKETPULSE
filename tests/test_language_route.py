from fastapi.testclient import TestClient

from app.entrypoint import app


client = TestClient(app)


def test_language_route_rejects_external_redirects_and_unknown_locale():
    response = client.get('/set-language', params={'lang': 'xx', 'next': 'https://evil.example'}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/'
    assert 'predibeacon_lang=en' in response.headers['set-cookie']
