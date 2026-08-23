from app.services.home_card_localization import enhance_home_card_localization


def test_dynamic_card_localization_covers_customer_facing_labels_by_locale():
    enhanced = enhance_home_card_localization('<html><body><div id="grid"></div><p id="count"></p></body></html>')

    for phrase in (
        "document.documentElement.lang",
        "en:{open:'Open',closed:'Closed'",
        "'pt-br':{open:'Aberto',closed:'Encerrado'",
        "es:{open:'Abierto',closed:'Cerrado'",
        "analysis:'View PrediBeacon analysis'",
        "analysis:'Ver análise PrediBeacon'",
        "analysis:'Ver análisis PrediBeacon'",
        "watch:'Watch',watching:'Watching'",
        "watch:'Acompanhar',watching:'Acompanhando'",
        "watch:'Seguir',watching:'Siguiendo'",
    ):
        assert phrase in enhanced


def test_dynamic_card_localization_handles_new_cards_and_count_updates():
    enhanced = enhance_home_card_localization('<html><body><div id="grid"></div><p id="count"></p></body></html>')

    assert 'new MutationObserver(scan).observe(grid,{childList:true,subtree:true})' in enhanced
    assert "card.dataset.locale=document.documentElement.lang||'en'" in enhanced
    assert "catalog[locale]||catalog.en" in enhanced
    assert "m[1]==='1'?t.market:t.markets" in enhanced
    assert "count.textContent=t.unavailable" in enhanced
    assert "card.dataset.locale='pt-BR'" not in enhanced


def test_dynamic_card_localization_is_idempotent():
    source = '<html><body><div id="grid"></div></body></html>'
    once = enhance_home_card_localization(source)
    twice = enhance_home_card_localization(once)

    assert once == twice
    assert once.count('predibeacon-home-card-localization-script') == 1
