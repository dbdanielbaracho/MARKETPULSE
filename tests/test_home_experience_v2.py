from app.services.home_experience_v2 import enhance_home_v2


def _base_home() -> str:
    return '''<html><head></head><body>
    <section class="hero wrap"></section>
    <section id="markets">
      <div class="controls">
        <label><select id="sort"><option value="trending">Most relevant</option><option value="movers">Biggest movers</option><option value="volume">Most volume</option></select></label>
        <label><select id="venue"><option value="">All</option><option value="kalshi">Kalshi</option><option value="polymarket">Polymarket</option></select></label>
      </div>
      <div id="grid"></div>
    </section>
    </body></html>'''


def test_home_v2_adds_two_functional_venue_entry_points():
    enhanced = enhance_home_v2(_base_home())

    assert 'data-venue-link="kalshi"' in enhanced
    assert 'data-venue-link="polymarket"' in enhanced
    assert 'venue.value=a.dataset.venueLink' in enhanced
    assert "venue.dispatchEvent(new Event('change'" in enhanced
    assert 'Explorar Kalshi' in enhanced
    assert 'Explorar Polymarket' in enhanced


def test_home_v2_uses_real_status_and_market_endpoints():
    enhanced = enhance_home_v2(_base_home())

    assert "fetch('/api/v1/status')" in enhanced
    assert "fetch('/api/v1/markets?sort=movers&limit=1')" in enhanced
    assert "fetch('/api/v1/markets?sort=volume&limit=1')" in enhanced
    assert "fetch('/api/v1/compare/pairs?limit=12&candidate_limit=24')" in enhanced
    assert 'venue_market_counts?.kalshi' in enhanced
    assert 'venue_market_counts?.polymarket' in enhanced


def test_home_v2_quick_filters_drive_existing_sort_control():
    enhanced = enhance_home_v2(_base_home())

    for value in ('trending', 'movers', 'volume'):
        assert f'data-q="{value}"' in enhanced
    assert 'sort.value=b.dataset.q' in enhanced
    assert "sort.dispatchEvent(new Event('change'" in enhanced


def test_home_v2_explains_product_value_without_fake_market_examples():
    enhanced = enhance_home_v2(_base_home())

    assert 'Kalshi + Polymarket, priorizados, comparados e explicados em um só lugar.' in enhanced
    assert 'Nós analisamos.' in enhanced
    assert 'Você decide.' in enhanced
    assert 'Trump' not in enhanced
    assert 'Bitcoin' not in enhanced
    assert 'GPT-5' not in enhanced


def test_home_v2_is_idempotent():
    once = enhance_home_v2(_base_home())
    twice = enhance_home_v2(once)

    assert once == twice
    assert once.count('predibeacon-home-v2-script') == 1
    assert once.count('predibeacon-home-v2-style') == 1
