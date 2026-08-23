from app.services.home_card_localization import enhance_home_card_localization


def test_dynamic_card_localization_covers_customer_facing_labels():
    enhanced = enhance_home_card_localization('<html><body><div id="grid"></div><p id="count"></p></body></html>')

    for phrase in (
        "text(status,'Open','Aberto')",
        "text(status,'Closed','Encerrado')",
        '<strong>Por que importa:</strong>',
        "first.textContent='Volume '",
        "first.textContent='Fecha em '",
        "first.textContent='Relevância '",
        "text(primary,'View PrediBeacon analysis','Ver análise PrediBeacon')",
        "text(watch,'Watch','Acompanhar')",
        "text(watch,'Watching','Acompanhando')",
    ):
        assert phrase in enhanced


def test_dynamic_card_localization_handles_new_cards_and_count_updates():
    enhanced = enhance_home_card_localization('<html><body><div id="grid"></div><p id="count"></p></body></html>')

    assert 'new MutationObserver(scan).observe(grid,{childList:true,subtree:true})' in enhanced
    assert "card.dataset.locale='pt-BR'" in enhanced
    assert ".replace(/\\bmarkets\\b/g,'mercados')" in enhanced
    assert ".replace(/\\bmarket\\b/g,'mercado')" in enhanced
    assert ".replace('Unavailable','Indisponível')" in enhanced


def test_dynamic_card_localization_is_idempotent():
    source = '<html><body><div id="grid"></div></body></html>'
    once = enhance_home_card_localization(source)
    twice = enhance_home_card_localization(once)

    assert once == twice
    assert once.count('predibeacon-home-card-localization-script') == 1
