from app.services.home_interaction_fixes import enhance_home_interactions


def _home() -> str:
    return '''<html><head></head><body><section class="hero-v2"><div></div><div><div class="venue-hub"><a data-venue-link="kalshi"></a><button data-venue-link="all"></button><a data-venue-link="polymarket"></a></div></div></section><section id="markets"><select id="venue"><option value="">All</option><option value="kalshi">Kalshi</option><option value="polymarket">Polymarket</option></select></section></body></html>'''


def test_home_interactions_make_all_three_views_navigable():
    out = enhance_home_interactions(_home())
    assert "hrefFor=v=>v==='all'?'/?venue=all#markets'" in out
    assert "location.assign(target)" in out
    assert "e.stopImmediatePropagation()" in out
    assert "venue.dispatchEvent(new Event('change',{bubbles:true}))" in out
    assert "markets.scrollIntoView({behavior:'smooth',block:'start'})" in out


def test_home_interactions_restore_direct_venue_links():
    out = enhance_home_interactions(_home())
    assert "const initial=normalized(params.get('venue'))" in out
    assert "if(params.has('venue'))" in out
    assert "syncSelected(initial)" in out
    assert "Ver todos os mercados Kalshi" in out
    assert "Ver todos os mercados Polymarket" in out
    assert "Ver Kalshi e Polymarket juntos" in out


def test_home_layout_avoids_fragile_fixed_minimum_columns():
    out = enhance_home_interactions(_home())
    assert 'grid-template-columns:minmax(0,.9fr) minmax(0,1.3fr)' in out
    assert '@media(max-width:980px){.hero-v2{grid-template-columns:1fr}' in out
    assert '.hero-v2>div{min-width:0}' in out
    assert '.venue-card,.beacon-core{width:100%;box-sizing:border-box}' in out


def test_home_interaction_enhancement_is_idempotent():
    once = enhance_home_interactions(_home())
    twice = enhance_home_interactions(once)
    assert once == twice
    assert once.count('predibeacon-home-interaction-fixes-script') == 1
    assert once.count('predibeacon-home-interaction-fixes-style') == 1
