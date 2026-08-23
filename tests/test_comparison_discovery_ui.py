from pathlib import Path


INDEX = Path("app/templates/index.html")
TOP = Path("app/templates/top.html")


def test_homepage_uses_bounded_server_side_pair_discovery():
    source = INDEX.read_text(encoding="utf-8")
    assert "/api/v1/compare/pairs?" in source
    assert "candidate_limit:'24'" in source
    assert "Comparison candidate found, but equivalence is not verified" in source
    assert "Unverified lookalikes are excluded" in source
    assert "candidate discovery can match close wording" in source.casefold()


def test_intelligence_uses_verified_pair_discovery_not_exact_title_loop():
    source = TOP.read_text(encoding="utf-8")
    assert "/api/v1/compare/pairs?" in source
    assert "verified_only:'true'" in source
    assert "norm(a.title)===norm(b.title)" not in source
    assert "Verified confidence" in source
