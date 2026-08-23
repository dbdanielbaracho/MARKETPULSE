from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.main import DiscoveryMarket, set_discovery_markets
from app.services.public_locale import SUPPORTED_LOCALES


client = TestClient(app)


def test_english_is_default_and_language_selector_lists_supported_locales():
    client.cookies.clear()
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-language"] == "en"
    assert '<html lang="en">' in page.text
    assert "REAL-TIME MARKET INTELLIGENCE" in page.text
    assert "Choose a view" in page.text
    assert "INTELIGÊNCIA DE MERCADO EM TEMPO REAL" not in page.text
    for locale in SUPPORTED_LOCALES:
        assert f"/set-language?lang={locale}" in page.text


def test_language_choice_persists_in_cookie_and_redirect_is_safe():
    client.cookies.clear()
    response = client.get("/set-language", params={"lang": "pt-BR", "next": "/top"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/top"
    assert "predibeacon_lang=pt-BR" in response.headers["set-cookie"]
    unsafe = client.get("/set-language", params={"lang": "es", "next": "//evil.example"}, follow_redirects=False)
    assert unsafe.headers["location"] == "/"


def test_portuguese_and_spanish_are_controlled_translations_not_browser_translation():
    client.cookies.clear()
    pt = client.get("/", cookies={"predibeacon_lang": "pt-BR"})
    assert pt.headers["content-language"] == "pt-BR"
    assert '<html lang="pt-BR">' in pt.text
    assert "INTELIGÊNCIA DE MERCADO EM TEMPO REAL" in pt.text
    assert "Escolha uma visão" in pt.text
    assert ">Resumos<" in pt.text

    es = client.get("/", cookies={"predibeacon_lang": "es"})
    assert es.headers["content-language"] == "es"
    assert '<html lang="es">' in es.text
    assert "INTELIGENCIA DE MERCADO EN TIEMPO REAL" in es.text
    assert "Elige una vista" in es.text
    assert ">Resúmenes<" in es.text


def test_other_languages_are_selectable_and_unknown_locale_falls_back_to_english():
    client.cookies.clear()
    for locale in ("fr", "de", "it", "ja", "ko", "zh-CN"):
        page = client.get("/", cookies={"predibeacon_lang": locale})
        assert page.status_code == 200
        assert page.headers["content-language"] == locale
        assert f'<html lang="{locale}">' in page.text
        assert f"🌐 {locale.split('-')[0].upper() if locale != 'zh-CN' else 'ZH'}" in page.text

    fallback = client.get("/", cookies={"predibeacon_lang": "xx"})
    assert fallback.headers["content-language"] == "en"
    assert '<html lang="en">' in fallback.text


def test_arabic_sets_rtl_direction():
    client.cookies.clear()
    page = client.get("/", cookies={"predibeacon_lang": "ar"})
    assert page.headers["content-language"] == "ar"
    assert '<html lang="ar" dir="rtl">' in page.text
    assert "الأسواق" in page.text


def test_market_contract_title_is_preserved_when_ui_language_changes():
    client.cookies.clear()
    title = "Will the Federal Reserve cut rates before December 2026?"
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:i18n-title",
            title=title,
            venue="kalshi",
            probability=.55,
            trend_score=80,
            observed_at=datetime.now(timezone.utc),
        )
    ])
    page = client.get("/market", params={"market_id": "kalshi:i18n-title"}, cookies={"predibeacon_lang": "pt-BR"})
    assert page.status_code == 200
    # The provider/contract title remains original in SEO and in the API; UI localization does not rewrite identity.
    assert title in page.text
    api = client.get("/api/v1/market", params={"market_id": "kalshi:i18n-title"})
    assert api.json()["title"] == title


def test_locale_dependent_public_html_varies_on_cookie():
    client.cookies.clear()
    page = client.get("/alerts", cookies={"predibeacon_lang": "es"})
    assert page.headers["vary"]
    assert "Cookie" in page.headers["vary"]
    assert page.headers["content-language"] == "es"
