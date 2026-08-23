from app.services.public_locale_extended import extend_public_translation


def test_watchlist_portuguese_and_spanish_translate_static_and_dynamic_copy():
    source = "Watchlist — PrediBeacon YOUR INTELLIGENCE >Watchlist< Markets you chose to follow, with current probability, movement and timing. Saved only in this browser. Loading saved markets… Your watchlist is empty. Explore current markets Change unavailable Trend  Reported volume Closes in Platform View analysis Create alert >Remove</button>"
    pt = extend_public_translation('/watchlist', source, 'pt-BR')
    assert 'Lista de observação — PrediBeacon' in pt
    assert 'SUA INTELIGÊNCIA' in pt
    assert 'Sua lista de observação está vazia.' in pt
    assert 'Ver análise' in pt
    assert 'Criar alerta' in pt
    assert '>Remover</button>' in pt

    es = extend_public_translation('/watchlist', source, 'es')
    assert 'Lista de seguimiento — PrediBeacon' in es
    assert 'TU INTELIGENCIA' in es
    assert 'Tu lista de seguimiento está vacía.' in es
    assert 'Ver análisis' in es
    assert 'Crear alerta' in es


def test_intelligence_portuguese_and_spanish_translate_high_value_sections():
    source = "PrediBeacon Intelligence Understand the market before choosing a venue. Top markets today Markets scanned Smart movers Breaking signals Newly observed Verified pairs Verified gaps WHAT MATTERS NOW BREAKING MARKETS FRESH MARKETS CATALYST MONITOR RESOLUTION CALENDAR MARKET QUALITY CATEGORY HEAT VERIFIED CONSENSUS VERIFIED DISAGREEMENTS VENUE COMPARISON Open analysis Attention Loading…"
    pt = extend_public_translation('/top', source, 'pt-BR')
    for phrase in ('Entenda o mercado antes de escolher uma plataforma.', 'Principais mercados de hoje', 'Mercados analisados', 'O QUE IMPORTA AGORA', 'CONSENSO VERIFICADO', 'DIVERGÊNCIAS VERIFICADAS', 'Abrir análise'):
        assert phrase in pt
    es = extend_public_translation('/top', source, 'es')
    for phrase in ('Entiende el mercado antes de elegir una plataforma.', 'Principales mercados de hoy', 'Mercados analizados', 'LO QUE IMPORTA AHORA', 'CONSENSO VERIFICADO', 'DIVERGENCIAS VERIFICADAS', 'Abrir análisis'):
        assert phrase in es


def test_additional_languages_have_essential_watchlist_and_intelligence_copy():
    for locale in ('fr', 'de', 'it', 'ja', 'ko', 'zh-CN', 'ar'):
        watch = extend_public_translation('/watchlist', 'YOUR INTELLIGENCE >Watchlist< View analysis', locale)
        top = extend_public_translation('/top', 'Understand the market before choosing a venue. Top markets today Open analysis', locale)
        assert watch != 'YOUR INTELLIGENCE >Watchlist< View analysis'
        assert top != 'Understand the market before choosing a venue. Top markets today Open analysis'


def test_english_and_unrelated_paths_remain_unchanged():
    source = 'Understand the market before choosing a venue. Watchlist'
    assert extend_public_translation('/top', source, 'en') == source
    assert extend_public_translation('/admin', source, 'pt-BR') == source
