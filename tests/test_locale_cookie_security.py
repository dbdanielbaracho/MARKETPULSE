from fastapi.testclient import TestClient

from app.entrypoint import app


def _cookie_header(base_url: str, headers: dict[str, str] | None = None) -> str:
    client = TestClient(app, base_url=base_url)
    response = client.get(
        "/set-language?lang=es&next=/",
        headers=headers or {},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    return response.headers["set-cookie"]


def test_locale_cookie_is_secure_on_https():
    cookie = _cookie_header("https://predibeacon.test")
    assert "predibeacon_lang=es" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie


def test_locale_cookie_honors_forwarded_https_at_tls_proxy_boundary():
    cookie = _cookie_header(
        "http://predibeacon.internal",
        {"x-forwarded-proto": "https"},
    )
    assert "Secure" in cookie


def test_local_http_development_does_not_receive_unusable_secure_cookie():
    cookie = _cookie_header("http://testserver")
    assert "Secure" not in cookie


def test_language_redirect_still_rejects_protocol_relative_destination():
    client = TestClient(app, base_url="https://predibeacon.test")
    response = client.get(
        "/set-language?lang=pt-BR&next=//evil.example",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
