from app.services.home_card_localization import SCRIPT as CARD_SCRIPT
from app.services.home_venue_context import SCRIPT as VENUE_SCRIPT


def test_dynamic_home_cards_respect_document_language():
    assert "document.documentElement.lang" in CARD_SCRIPT
    assert "'pt-br':" in CARD_SCRIPT
    assert "es:{" in CARD_SCRIPT
    assert "catalog[locale]||catalog.en" in CARD_SCRIPT
    assert "card.dataset.locale='pt-BR'" not in CARD_SCRIPT


def test_english_dynamic_card_labels_are_not_forced_to_portuguese():
    assert "en:{open:'Open',closed:'Closed'" in CARD_SCRIPT
    assert "analysis:'View PrediBeacon analysis'" in CARD_SCRIPT
    assert "watch:'Watch',watching:'Watching'" in CARD_SCRIPT


def test_platform_context_uses_selected_language_with_english_fallback():
    assert "document.documentElement.lang" in VENUE_SCRIPT
    assert "catalogs[locale]||catalogs.en" in VENUE_SCRIPT
    assert "en:{platformView:'Platform view'" in VENUE_SCRIPT
    assert "'pt-br':{platformView:'Visão da plataforma'" in VENUE_SCRIPT
    assert "es:{platformView:'Vista de la plataforma'" in VENUE_SCRIPT
