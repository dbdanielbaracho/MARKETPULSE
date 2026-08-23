from app.services.public_locale import localize_public_html


def test_market_journey_is_localized_without_script_injection():
    source = '''<html lang="en"><body>← Back to markets CURRENT MARKET SIGNAL Trend score Reported volume Time remaining Last observed Open platform ↗ Add to watchlist Create alert Copy market link MARKET QUALITY CROSS-PLATFORM CHECK WHY IT MATTERS Probability history Market timeline Related markets<script>const a='Remove from watchlist',b='Probability unavailable',c='This market is temporarily unavailable. PrediBeacon will not substitute a different contract.';</script></body></html>'''
    out = localize_public_html('/market', source)

    assert '<html lang="pt-BR">' in out
    for phrase in ('Voltar aos mercados', 'SINAL ATUAL DO MERCADO', 'Relevância', 'Volume informado', 'Tempo restante', 'Última observação', 'Abrir plataforma', 'Adicionar à lista de observação', 'Criar alerta', 'Copiar link do mercado', 'QUALIDADE DO MERCADO', 'VERIFICAÇÃO ENTRE PLATAFORMAS', 'POR QUE IMPORTA', 'Histórico de probabilidade', 'Linha do tempo do mercado', 'Mercados relacionados', 'Remover da lista de observação', 'Probabilidade indisponível', 'A PrediBeacon não substituirá por outro contrato'):
        assert phrase in out
    assert '<script id="' not in out


def test_market_slug_route_uses_same_locale():
    source = '<html lang="en"><body>← Back to markets Probability history</body></html>'
    out = localize_public_html('/markets/example-market', source)
    assert 'Voltar aos mercados' in out
    assert 'Histórico de probabilidade' in out


def test_alert_journey_localizes_static_and_dynamic_states():
    source = '''<html lang="en"><body>← Markets FOLLOW WHAT MATTERS Market alerts Get a browser notification while PrediBeacon is open when a market you follow reaches your probability threshold. Preferences stay in this browser. Create an alert Loading markets… Create alert Saved alerts<script>const a='Choose a market first.',b='Alert saved for ',c='Current probability unavailable';</script></body></html>'''
    out = localize_public_html('/alerts', source)

    for phrase in ('← Mercados', 'ACOMPANHE O QUE IMPORTA', 'Alertas de mercado', 'Receba uma notificação no navegador', 'Criar um alerta', 'Carregando mercados', 'Criar alerta', 'Alertas salvos', 'Escolha um mercado primeiro', 'Alerta salvo para', 'Probabilidade atual indisponível'):
        assert phrase in out


def test_unrelated_html_is_not_modified():
    source = '<html lang="en"><body>Market alerts Probability history</body></html>'
    assert localize_public_html('/admin', source) == source
