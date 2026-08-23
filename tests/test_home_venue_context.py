from app.services.home_venue_context import enhance_home_venue_context


def test_venue_context_is_added_once_and_hidden_for_combined_view():
    source = '<html><head></head><body><section id="markets"><div class="quick-filters"></div></section></body></html>'
    once = enhance_home_venue_context(source)
    twice = enhance_home_venue_context(once)

    assert once == twice
    assert 'id="predibeacon-venue-context-script"' in once
    assert 'id="predibeacon-venue-context-style"' in once
    assert "if(which==='all'){panel.dataset.visible='false';return}" in once


def test_venue_context_fetches_real_platform_rankings():
    enhanced = enhance_home_venue_context('<html><head></head><body><section id="markets"></section></body></html>')

    assert '/api/v1/markets?venue=${venue}&sort=trending&limit=1' in enhanced
    assert '/api/v1/markets?venue=${venue}&sort=movers&limit=1' in enhanced
    assert '/api/v1/markets?venue=${venue}&sort=volume&limit=1' in enhanced
    assert '/api/v1/markets/closing-soon?venue=${venue}&limit=1' in enhanced
    assert 'Mais relevante' in enhanced
    assert 'Maior movimento' in enhanced
    assert 'Maior atividade' in enhanced
    assert 'Fecha primeiro' in enhanced


def test_venue_context_has_honest_failure_state():
    enhanced = enhance_home_venue_context('<html><head></head><body><section id="markets"></section></body></html>')

    assert 'Resumo da plataforma temporariamente indisponível.' in enhanced
    assert 'Os mercados abaixo continuam acessíveis.' in enhanced
    assert 'Nenhum dado disponível agora' in enhanced
