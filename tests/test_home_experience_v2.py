from app.services.home_experience_v2 import enhance_home_v2


def _base_home() -> str:
    return '''<html><head></head><body><section class="hero wrap"></section><section id="markets"><div class="controls"><label><select id="sort"><option value="trending">Most relevant</option><option value="movers">Biggest movers</option><option value="volume">Most volume</option></select></label><label><select id="venue"><option value="">All</option><option value="kalshi">Kalshi</option><option value="polymarket">Polymarket</option></select></label></div><p id="count"></p><div id="state"></div><div id="grid"></div></section></body></html>'''


def test_home_v2_has_three_explicit_clickable_views():
    enhanced = enhance_home_v2(_base_home())
    for value in ('kalshi', 'all', 'polymarket'):
        assert f'data-venue-link="{value}"' in enhanced
    assert 'Escolha uma visão' in enhanced
    assert 'Clique em Kalshi, PrediBeacon ou Polymarket para explorar.' in enhanced
    assert 'Explorar Kalshi' in enhanced
    assert 'Ver visão completa' in enhanced
    assert 'Explorar Polymarket' in enhanced
    assert 'function setVision(which)' in enhanced
    assert "const value=which==='all'?'':which" in enhanced
    assert "venue.value=value" in enhanced


def test_home_v2_venue_cards_have_real_data_charts_not_static_fake_numbers():
    enhanced = enhance_home_v2(_base_home())
    assert 'class="venue-chart"' in enhanced
    assert "fetch('/api/v1/markets?venue=kalshi&sort=trending&limit=24')" in enhanced
    assert "fetch('/api/v1/markets?venue=polymarket&sort=trending&limit=24')" in enhanced
    assert 'function marketSeries(items)' in enhanced
    assert 'function drawChart(id,values)' in enhanced
    assert 'venue_market_counts?.kalshi' in enhanced
    assert 'venue_market_counts?.polymarket' in enhanced


def test_home_v2_uses_real_status_and_market_endpoints():
    enhanced = enhance_home_v2(_base_home())
    assert "fetch('/api/v1/status')" in enhanced
    assert "fetch('/api/v1/markets?sort=movers&limit=1')" in enhanced
    assert "fetch('/api/v1/markets?sort=volume&limit=1')" in enhanced
    assert "fetch('/api/v1/compare/pairs?limit=12&candidate_limit=24')" in enhanced
    assert "fetch('/api/v1/markets/closing-soon?'" in enhanced


def test_home_v2_quick_filters_are_functional():
    enhanced = enhance_home_v2(_base_home())
    for value in ('trending', 'movers', 'volume', 'closing'):
        assert f'data-q="{value}"' in enhanced
    assert 'Terminando em breve' in enhanced
    assert 'sort.value=activeMode' in enhanced
    assert "if(activeMode==='closing')loadClosing()" in enhanced
    assert "if(venue?.value)q.set('venue',venue.value)" in enhanced


def test_home_v2_closing_mode_has_honest_empty_and_error_states():
    enhanced = enhance_home_v2(_base_home())
    assert 'Nenhum mercado com prazo conhecido está fechando em breve.' in enhanced
    assert 'O ranking por prazo está temporariamente indisponível.' in enhanced
    assert "if(!r.ok)throw 0" in enhanced


def test_home_v2_structures_desktop_market_rows_without_removing_controls():
    enhanced = enhance_home_v2(_base_home())
    assert 'function structureCards()' in enhanced
    assert "market.className='market-summary'" in enhanced
    assert "prediction.className='prediction-summary'" in enhanced
    assert "c.dataset.homeRow='ready'" in enhanced
    assert 'grid-template-areas:"market prediction facts venue actions"' in enhanced
    assert 'new MutationObserver(structureCards)' in enhanced


def test_home_v2_uses_css_beacon_and_accessible_interactions():
    enhanced = enhance_home_v2(_base_home())
    assert 'class="beacon-graphic"' in enhanced
    assert 'class="beacon-light"' in enhanced
    assert 'type="button" class="beacon-core"' in enhanced
    assert 'aria-label="Ver visão completa PrediBeacon"' in enhanced
    assert ':focus-visible' in enhanced
    assert '♜' not in enhanced


def test_home_v2_explains_product_value_without_fake_market_examples():
    enhanced = enhance_home_v2(_base_home())
    assert 'Kalshi + Polymarket, priorizados, comparados e explicados em um só lugar.' in enhanced
    assert 'Trump' not in enhanced
    assert 'Bitcoin' not in enhanced
    assert 'GPT-5' not in enhanced


def test_home_v2_is_idempotent():
    once = enhance_home_v2(_base_home())
    twice = enhance_home_v2(once)
    assert once == twice
    assert once.count('predibeacon-home-v2-script') == 1
    assert once.count('predibeacon-home-v2-style') == 1
