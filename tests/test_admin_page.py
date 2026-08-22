from app.main import admin_page


def test_admin_page_uses_nonce_and_security_headers():
    response = admin_page()
    body = response.body.decode()

    assert "MarketPulse · Editorial review" in body
    assert "__CSP_NONCE__" not in body
    assert "localStorage" not in body
    assert "sessionStorage" not in body
    assert "Publish manually" in body
    assert "Rollback" in body
    assert "Approval never publishes automatically" in body
    assert "/api/v1/admin/publications" in body
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_admin_page_generates_a_fresh_nonce_per_response():
    first = admin_page()
    second = admin_page()

    assert first.headers["content-security-policy"] != second.headers["content-security-policy"]
