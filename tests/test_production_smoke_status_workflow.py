from pathlib import Path


def test_production_smoke_publishes_verifiable_commit_status():
    workflow = Path(".github/workflows/production-smoke.yml").read_text(encoding="utf-8")
    assert "statuses: write" in workflow
    assert "id: production_smoke" in workflow
    # The live production suite is a hard release gate. It must never be masked
    # with continue-on-error; the always-running publisher can still record the
    # failing commit status after the test step fails.
    assert "continue-on-error: true" not in workflow
    assert "if: always()" in workflow
    assert "predibeacon/production-browser-smoke" in workflow
    assert "github.event.workflow_run.head_sha" in workflow
    assert "/statuses/${target_sha}" in workflow
    assert "target_url=" in workflow
    assert 'if [[ "${state}" != "success" ]]' in workflow


def test_production_smoke_still_runs_all_required_live_browser_suites():
    workflow = Path(".github/workflows/production-smoke.yml").read_text(encoding="utf-8")
    assert "browser_e2e/test_production_smoke.py" in workflow
    assert "browser_e2e/test_production_home_quality.py" in workflow
    assert "browser_e2e/test_production_mobile.py" in workflow
    assert "browser_e2e/test_production_outbound.py" in workflow
    assert "browser_e2e/test_production_homepage_quality.py" in workflow
    assert "https://predibeacon.com" in workflow
