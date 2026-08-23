from pathlib import Path


INDEX_TEMPLATE = Path("app/templates/index.html")


def test_comparator_reports_when_other_platform_has_no_verified_equivalent():
    source = INDEX_TEMPLATE.read_text(encoding="utf-8")

    assert "MATCH ON OTHER PLATFORM" in source
    assert "No verified equivalent contract is currently available on the other platform." in source
    assert "Compare verified contracts" in source
    assert "compareSecond.hidden=true" in source
    assert "m.venue!==selected.venue" in source
    assert "normalizedContractTitle(m.title)===normalizedContractTitle(selected.title)" in source
