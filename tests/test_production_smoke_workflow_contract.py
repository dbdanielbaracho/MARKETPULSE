from pathlib import Path


def test_production_smoke_does_not_cancel_in_progress_evidence_run():
    workflow = Path('.github/workflows/production-smoke.yml').read_text(encoding='utf-8')
    assert 'group: production-browser-smoke' in workflow
    assert 'cancel-in-progress: false' in workflow
    assert 'cancel-in-progress: true' not in workflow


def test_production_smoke_still_runs_all_real_acceptance_suites():
    workflow = Path('.github/workflows/production-smoke.yml').read_text(encoding='utf-8')
    for command in (
        'pytest -q browser_e2e/test_production_smoke.py',
        'pytest -q browser_e2e/test_production_mobile.py',
        'pytest -q browser_e2e/test_production_outbound.py',
    ):
        assert command in workflow
    assert 'context="predibeacon/production-browser-smoke"' in workflow
