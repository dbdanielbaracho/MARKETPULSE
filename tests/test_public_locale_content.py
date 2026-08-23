from app.services.public_locale_content import translate_content_shell


def test_articles_shell_translates_without_touching_injected_article_content():
    source = '<html><body>PREDIBEACON BRIEFS Editorial intelligence, with evidence. __ARTICLE_CONTENT__ Prediction market intelligence</body></html>'
    pt = translate_content_shell('/articles', source, 'pt-BR')
    assert 'RESUMOS PREDIBEACON' in pt
    assert 'Inteligência editorial, com evidências.' in pt
    assert 'Inteligência de mercados de previsão' in pt
    assert '__ARTICLE_CONTENT__' in pt


def test_article_detail_translates_shell_but_preserves_article_placeholders():
    source = '<html><body>← All briefs PREDIBEACON BRIEF __ARTICLE_HEADING__ __ARTICLE_BODY__ <h2>Sources</h2> Prediction-market prices can change. PrediBeacon provides informational market intelligence and does not guarantee outcomes.</body></html>'
    es = translate_content_shell('/articles/example', source, 'es')
    assert '← Todos los resúmenes' in es
    assert 'RESUMEN PREDIBEACON' in es
    assert '>Fuentes<' in es
    assert '__ARTICLE_HEADING__' in es
    assert '__ARTICLE_BODY__' in es


def test_creator_shell_translates_dynamic_ui_strings_but_not_market_titles():
    market_title = 'Will the Federal Reserve cut rates before December 2026?'
    source = f'<html><body>Creator markets Loading… Markets selected by @ Trend Explore market No active market selections are available. {market_title}</body></html>'
    pt = translate_content_shell('/creator/alice', source, 'pt-BR')
    assert 'Mercados do creator' in pt
    assert 'Carregando…' in pt
    assert 'Mercados selecionados por @' in pt
    assert 'Explorar mercado' in pt
    assert market_title in pt


def test_english_is_canonical_and_unchanged():
    source = '<html><body>Editorial intelligence, with evidence. Creator markets Explore market</body></html>'
    assert translate_content_shell('/articles', source, 'en') == source
    assert translate_content_shell('/creator/alice', source, 'en') == source


def test_unsupported_content_shell_path_is_unchanged():
    source = '<html><body>Editorial intelligence, with evidence.</body></html>'
    assert translate_content_shell('/admin', source, 'pt-BR') == source
