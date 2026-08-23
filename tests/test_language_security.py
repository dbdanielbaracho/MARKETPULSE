from fastapi.testclient import TestClient

from app.entrypoint import app


client = TestClient(app)


def test_language_cookie_is_scoped_to_site():
    response = client.get('/set-language', params={'lang': 'es', 'next': '/'}, follow_redirects=False)
    cookie = response.headers['set-cookie']
    assert 'Path=/' in cookie
    assert 'SameSite=lax' in cookie
    assert response.headers['cache-control'] == 'no-store'
