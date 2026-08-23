from pathlib import Path


ENTRYPOINT = Path("app/entrypoint.py")
MIDDLEWARE = Path("app/middleware/relevance_pages.py")


def test_entrypoint_registers_relevance_page_middleware():
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert "register_relevance_pages_middleware" in source
    assert "register_relevance_pages_middleware(app)" in source


def test_relevance_middleware_targets_home_and_intelligence_only():
    source = MIDDLEWARE.read_text(encoding="utf-8")
    assert 'path not in {"/", "/top"}' in source
    assert "enhance_relevance_pages(body, path=path)" in source
