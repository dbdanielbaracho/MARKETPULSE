from app.services.public_locale import LOCALE_LABELS


def test_selector_uses_native_language_names():
    assert LOCALE_LABELS == {
        'en': 'English',
        'es': 'Español',
        'pt-BR': 'Português',
        'fr': 'Français',
        'de': 'Deutsch',
        'it': 'Italiano',
        'ja': '日本語',
        'ko': '한국어',
        'zh-CN': '简体中文',
        'ar': 'العربية',
    }
