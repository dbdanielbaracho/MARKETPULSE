from app.services.home_page_enhancements import enhance_home_template


def test_home_enhancer_adds_visible_cross_platform_status():
    source = '<html><head></head><body><div id="grid"></div></body></html>'
    enhanced = enhance_home_template(source)

    assert 'platform-availability' in enhanced
    assert 'Available on ${venueLabel(venue)}' in enhanced
    assert 'No verified equivalent found on ${other}' in enhanced
    assert 'Similar market found on ${venueLabel(counterpart.venue)}, but it is not verified as the same contract.' in enhanced
    assert 'verified equivalent' in enhanced
    assert '/api/v1/market/cross-platform?' in enhanced
    assert "candidate_limit:'3'" in enhanced


def test_home_enhancer_uses_lazy_lookup_and_is_idempotent():
    source = '<html><head></head><body><div id="grid"></div></body></html>'
    enhanced = enhance_home_template(source)
    enhanced_twice = enhance_home_template(enhanced)

    assert 'IntersectionObserver' in enhanced
    assert 'MutationObserver' in enhanced
    assert enhanced_twice == enhanced
    assert enhanced.count('predibeacon-home-platform-visibility-script') == 1
