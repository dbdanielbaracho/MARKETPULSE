from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).parents[1]
client = TestClient(app)


def test_market_timeline_script_is_well_formed():
    template = (ROOT / "app" / "templates" / "market.html").read_text(encoding="utf-8")
    assert "· </script></body></html>+" not in template
    assert "Math.round(e.volume_usd).toLocaleString('en-US')" in template


def test_service_worker_never_caches_sensitive_routes():
    worker = (ROOT / "app" / "static" / "service-worker.js").read_text(encoding="utf-8")
    for prefix in ("/api/", "/admin", "/out/", "/go/", "/articles"):
        assert prefix in worker
    assert "predibeacon-v3" in worker
    assert "NEVER_CACHE.some" in worker


def test_baseline_security_headers_are_global_and_admin_is_no_store():
    public = client.get("/health")
    assert public.headers["x-content-type-options"] == "nosniff"
    assert public.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in public.headers["permissions-policy"]
    assert public.headers["strict-transport-security"].startswith("max-age=")

    protected = client.get("/api/v1/admin/operations")
    assert protected.headers["cache-control"] == "no-store"
