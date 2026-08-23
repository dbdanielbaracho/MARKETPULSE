from app.services.home_page_enhancements import enhance_home_template


def test_home_enhancement_uses_native_portuguese_labels():
    source = '''<html lang="en"><head></head><body>
    <nav><a href="/articles">Briefs</a></nav>
    <section id="markets"><div class="section-title"><h2>Most relevant markets now</h2></div>
    <label><span class="eyebrow">SORT</span><select id="sort"><option value="trending">Most relevant</option><option value="movers">Biggest movers</option><option value="volume">Most volume</option></select></label>
    <label><span class="eyebrow">PLATFORM</span><select id="venue"></select></label><div id="grid"></div></section>
    <section id="disagreements"><h3>Biggest verified disagreements</h3></section></body></html>'''
    enhanced = enhance_home_template(source)

    assert '<html lang="pt-BR">' in enhanced
    assert '>Resumos</a>' in enhanced
    assert 'Mercados que merecem atenção agora' in enhanced
    assert 'Onde Kalshi e Polymarket mais discordam' in enhanced
    assert 'Relevância PrediBeacon' in enhanced
    assert 'Maiores movimentos de probabilidade' in enhanced
    assert 'Maior volume informado' in enhanced
    assert "venueFilter.textContent='PLATAFORMA'" in enhanced


def test_cross_platform_messages_are_native_portuguese():
    enhanced = enhance_home_template('<html><head></head><body><div id="grid"></div></body></html>')

    for phrase in (
        'Disponível na ${venueLabel(venue)}',
        'Verificando ${otherVenue(venue)} para o mesmo contrato',
        'Também na ${venueLabel(counterpart.venue)} · equivalente verificado',
        'Mercado semelhante encontrado na ${venueLabel(counterpart.venue)}, mas não foi verificado como o mesmo contrato.',
        'Nenhum equivalente verificado encontrado na ${other}.',
        'Verificação entre plataformas temporariamente indisponível.',
        'Confiança da verificação ${verification.confidence}/100.',
    ):
        assert phrase in enhanced


def test_home_does_not_reintroduce_ambiguous_or_primary_english_labels():
    enhanced = enhance_home_template('<html><head></head><body><nav><a href="/articles">Briefs</a></nav><div id="grid"></div></body></html>')

    assert '>Briefs</a>' not in enhanced
    assert 'Markets worth watching now' not in enhanced
    assert 'Where Kalshi and Polymarket disagree most' not in enhanced
    assert 'Available on ${venueLabel(venue)}' not in enhanced
