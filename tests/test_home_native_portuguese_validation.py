from app.services.home_page_enhancements import enhance_home_template


def test_native_portuguese_enhancement_is_idempotent_and_preserves_language():
    source = '<html lang="en"><head></head><body><nav><a href="/articles">Briefs</a></nav><section id="markets"><div class="section-title"><h2>Most relevant markets now</h2></div><div id="grid"></div></section></body></html>'
    once = enhance_home_template(source)
    twice = enhance_home_template(once)

    assert once == twice
    assert '<html lang="pt-BR">' in once
    assert '>Resumos</a>' in once
    assert once.count('predibeacon-home-platform-visibility-script') == 1
    assert once.count('predibeacon-home-platform-visibility-style') == 1
