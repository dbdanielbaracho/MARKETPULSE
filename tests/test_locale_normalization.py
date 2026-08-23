from app.services.public_locale import normalize_locale


def test_locale_aliases_and_unknown_values():
    assert normalize_locale(None) == "en"
    assert normalize_locale("pt") == "pt-BR"
    assert normalize_locale("PT-BR") == "pt-BR"
    assert normalize_locale("zh") == "zh-CN"
    assert normalize_locale("xx") == "en"
