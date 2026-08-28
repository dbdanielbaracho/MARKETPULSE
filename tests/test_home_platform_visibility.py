from app.services.home_page_enhancements import enhance_home_template


def test_home_enhancer_adds_visible_cross_platform_status():
    source = '<html><head></head><body><div id="grid"></div></body></html>'
    enhanced = enhance_home_template(source)

    assert 'platform-availability' in enhanced
    assert 'Disponível na ${venueLabel(venue)}' in enhanced
    assert 'Sem equivalente verificado na ${other}.' in enhanced
    assert "panel.classList.add('compact')" in enhanced
    assert '.platform-availability.compact' in enhanced
    assert 'Mercado semelhante encontrado na ${venueLabel(counterpart.venue)}, mas não foi verificado como o mesmo contrato.' in enhanced
    assert 'equivalente verificado' in enhanced
    assert '/api/v1/market/cross-platform?' in enhanced
    assert "candidate_limit:'3'" in enhanced


def test_home_enhancer_prioritizes_cards_over_duplicate_comparison_panel():
    source = '<html><head></head><body><div class="compare-panel"></div><section id="markets"><div class="section-title"><h2>Most relevant markets now</h2></div><div id="grid"></div></section><section id="disagreements"><h3>Biggest verified disagreements</h3></section></body></html>'
    enhanced = enhance_home_template(source)

    assert '.compare-panel{display:none!important}' in enhanced
    assert 'Mercados que merecem atenção agora' in enhanced
    assert 'Onde Kalshi e Polymarket mais discordam' in enhanced


def test_home_enhancer_explains_ranking_and_renames_sort_choices():
    source = '<html><head></head><body><section id="markets"><div class="controls"><label><span class="eyebrow">SORT</span><select id="sort"><option value="trending">Most relevant</option><option value="movers">Biggest movers</option><option value="volume">Most volume</option></select></label><label><span class="eyebrow">PLATFORM</span><select id="venue"></select></label></div><div class="section-title"><h2>Most relevant markets now</h2></div><div id="grid"></div></section></body></html>'
    enhanced = enhance_home_template(source)

    assert 'Por que esta ordem?' in enhanced
    assert 'Relevância PrediBeacon' in enhanced
    assert 'Maiores movimentos de probabilidade' in enhanced
    assert 'Maior volume informado' in enhanced
    assert "venueFilter.textContent='PLATAFORMA'" in enhanced
    assert 'movimento observado, atividade informada, proximidade do fechamento, atualização e qualidade dos dados' in enhanced


def test_home_enhancer_uses_resumos_instead_of_ambiguous_briefs_label():
    source = '<html><head></head><body><nav><a href="/articles">Briefs</a></nav><div id="grid"></div></body></html>'
    enhanced = enhance_home_template(source)

    assert '<a href="/articles">Resumos</a>' in enhanced
    assert '>Briefs</a>' not in enhanced


def test_home_enhancer_uses_lazy_lookup_and_is_idempotent():
    source = '<html><head></head><body><div id="grid"></div></body></html>'
    enhanced = enhance_home_template(source)
    enhanced_twice = enhance_home_template(enhanced)

    assert 'IntersectionObserver' in enhanced
    assert 'MutationObserver' in enhanced
    assert enhanced_twice == enhanced
    assert enhanced.count('predibeacon-home-platform-visibility-script') == 1
