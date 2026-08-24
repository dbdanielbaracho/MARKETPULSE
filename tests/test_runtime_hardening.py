from pathlib import Path
import re

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).parents[1]
client = TestClient(app)


def test_market_timeline_script_is_well_formed():
    template = (ROOT / "app" / "templates" / "market.html").read_text(encoding="utf-8")
    script_open = '<script nonce="__CSP_NONCE__">'

    assert template.count(script_open) == 1
    assert template.count("</script>") == 1
    assert template.endswith("</script></body></html>")
    script = template.split(script_open, 1)[1].rsplit("</script>", 1)[0]
    document_tail = template.rsplit("</script>", 1)[1]
    assert "async function loadTimeline()" in script
    assert "Math.round(event.volume_usd).toLocaleString('en-US')" in script
    assert "target.replaceChildren" in script
    assert "</body></html>" not in script
    assert document_tail == "</body></html>"
    assert '.period[aria-pressed="true"]' in template
    assert 'aria-live="polite"' in template
    assert "function drawHistory(points,hours)" in script
    assert "startT=endT-hours*60*60*1000" in script
    assert "setAttribute('aria-pressed'" in script
    assert "loadHistory(24)" in script


def test_service_worker_never_caches_sensitive_routes():
    worker = (ROOT / "app" / "static" / "service-worker.js").read_text(encoding="utf-8")
    for prefix in ("/api/", "/admin", "/out/", "/go/", "/articles"):
        assert prefix in worker
    assert re.search(r"predibeacon-v\d+", worker)
    assert "NEVER_CACHE.some" in worker


def test_baseline_security_headers_are_global_and_admin_is_no_store():
    public = client.get("/health")
    assert public.headers["x-content-type-options"] == "nosniff"
    assert public.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in public.headers["permissions-policy"]
    assert public.headers["strict-transport-security"].startswith("max-age=")

    protected = client.get("/api/v1/admin/operations")
    assert protected.headers["cache-control"] == "no-store"
