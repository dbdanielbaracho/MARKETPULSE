from app.services.public_locale import DEFAULT_LOCALE


def test_default_locale_is_english():
    assert DEFAULT_LOCALE == 'en'
