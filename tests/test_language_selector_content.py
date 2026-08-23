from app.services.public_locale import LOCALE_LABELS, SUPPORTED_LOCALES


def test_requested_languages_are_in_selector():
    assert SUPPORTED_LOCALES[:3] == ('en', 'es', 'pt-BR')
    assert LOCALE_LABELS['en'] == 'English'
    assert LOCALE_LABELS['es'] == 'Español'
    assert LOCALE_LABELS['pt-BR'] == 'Português'
    for locale in ('fr', 'de', 'it', 'ja', 'ko', 'zh-CN', 'ar'):
        assert locale in SUPPORTED_LOCALES
