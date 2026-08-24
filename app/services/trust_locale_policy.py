from __future__ import annotations


TRUST_PATHS = frozenset({"/methodology", "/risk", "/privacy", "/terms"})

# A non-English trust/legal page may be activated here only after its entire
# controlled copy has been reviewed as one coherent version. Partial string
# catalogs are intentionally not sufficient evidence for a legal-language claim.
REVIEWED_COMPLETE_TRANSLATIONS: frozenset[tuple[str, str]] = frozenset()


def trust_presentation_locale(path: str, requested_locale: str) -> str:
    """Return a truthful presentation language for trust/legal pages.

    Public product UI can fall back string-by-string. Trust/legal content cannot:
    if the requested page/locale is not explicitly reviewed as complete, present
    the canonical English version rather than a mixed-language document.
    """
    if path not in TRUST_PATHS or requested_locale == "en":
        return requested_locale
    if (path, requested_locale) in REVIEWED_COMPLETE_TRANSLATIONS:
        return requested_locale
    return "en"
