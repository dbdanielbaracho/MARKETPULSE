from app.middleware.public_locale import _locale_from_accept_language, _resolve_locale


def test_browser_portuguese_is_used_when_no_manual_cookie():
    assert _resolve_locale(None, "pt-BR,pt;q=0.9,en;q=0.8") == "pt-BR"


def test_browser_spanish_region_maps_to_supported_spanish():
    assert _resolve_locale(None, "es-MX,es;q=0.9,en;q=0.8") == "es"


def test_quality_weight_is_respected():
    assert _locale_from_accept_language("fr;q=0.4,en-US;q=0.9,pt-BR;q=0.8") == "en"


def test_manual_cookie_has_priority_over_browser_language():
    assert _resolve_locale("en", "pt-BR,pt;q=0.9") == "en"
    assert _resolve_locale("es", "en-US,en;q=0.9") == "es"


def test_simplified_chinese_browser_variants_map_to_supported_locale():
    assert _resolve_locale(None, "zh-Hans-CN,zh;q=0.9,en;q=0.5") == "zh-CN"


def test_unsupported_browser_language_falls_back_to_english():
    assert _resolve_locale(None, "nl-NL,nl;q=0.9") == "en"


def test_missing_browser_language_falls_back_to_english():
    assert _resolve_locale(None, None) == "en"
