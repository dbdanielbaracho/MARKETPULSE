from pathlib import Path

from app.services.public_locale import SUPPORTED_LOCALES
from app.services.public_locale_legal import PAGES, translate_legal_page


TEMPLATES = Path(__file__).parents[1] / "app" / "templates"
NON_ENGLISH = tuple(locale for locale in SUPPORTED_LOCALES if locale != "en")

PRIVACY_CANONICAL = (
    "Pre-launch privacy notice",
    "This notice describes the current public service.",
    "PrediBeacon does not currently offer public user accounts",
    "Hosting and security providers may process ordinary request data",
    "The private editorial interface keeps its token only in the current browser tab memory",
    "Opening a source or venue link sends the visitor to a third party",
    "Before enabling newsletters, personalized advertising",
    "The service is not designed to encourage minors",
)

TERMS_CANONICAL = (
    "Pre-launch terms of informational use",
    "These pre-launch terms are not the final commercial terms.",
    "PrediBeacon aggregates and explains public prediction-market information.",
    "PrediBeacon does not accept or safeguard user money",
    "Access to information does not establish eligibility",
    "Data can be delayed, incomplete or corrected.",
    "Third-party names and links identify sources or venues",
    "Users must not attack the service",
    "PrediBeacon branding, original explanations and software remain protected.",
    "Final entity information, contact details, governing law",
)


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_every_supported_non_english_locale_has_both_legal_pages():
    assert set(PAGES) == set(NON_ENGLISH)
    for locale in NON_ENGLISH:
        assert set(PAGES[locale]) == {"/privacy", "/terms"}


def test_privacy_visible_copy_is_fully_localized_for_every_non_english_locale():
    source = _template("privacy.html")
    for locale in NON_ENGLISH:
        result = translate_legal_page("/privacy", source, locale)
        assert result != source, locale
        assert "PrediBeacon" in result
        assert result.count("<h2>") == 6
        for fragment in PRIVACY_CANONICAL:
            assert fragment not in result, (locale, fragment)


def test_terms_visible_copy_is_fully_localized_for_every_non_english_locale():
    source = _template("terms.html")
    for locale in NON_ENGLISH:
        result = translate_legal_page("/terms", source, locale)
        assert result != source, locale
        assert "PrediBeacon" in result
        assert result.count("<h2>") == 8
        for fragment in TERMS_CANONICAL:
            assert fragment not in result, (locale, fragment)


def test_english_and_non_legal_pages_are_not_rewritten():
    privacy = _template("privacy.html")
    assert translate_legal_page("/privacy", privacy, "en") == privacy
    assert translate_legal_page("/methodology", privacy, "pt-BR") == privacy


def test_missing_main_fails_closed_without_partial_legal_translation():
    source = "<html><title>Privacy — PrediBeacon</title><body>broken template</body></html>"
    assert translate_legal_page("/privacy", source, "fr") == source
