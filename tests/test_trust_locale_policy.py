from fastapi.testclient import TestClient

from app.entrypoint import app
from app.services.trust_locale_policy import TRUST_PATHS, trust_presentation_locale


client = TestClient(app)


def test_unreviewed_trust_translations_fall_back_to_canonical_english():
    for path in TRUST_PATHS:
        for locale in ('pt-BR', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh-CN', 'ar'):
            assert trust_presentation_locale(path, locale) == 'en'


def test_non_trust_product_ui_keeps_requested_locale():
    for locale in ('pt-BR', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh-CN', 'ar'):
        assert trust_presentation_locale('/', locale) == locale
        assert trust_presentation_locale('/market', locale) == locale


def test_terms_page_never_claims_portuguese_while_serving_partial_legal_copy():
    response = client.get('/terms', cookies={'predibeacon_lang': 'pt-BR'})
    assert response.status_code == 200
    assert response.headers['content-language'] == 'en'
    assert response.headers['x-predibeacon-language-fallback'] == 'canonical-en'
    assert 'Pre-launch terms of informational use' in response.text
    assert 'Termos pré-lançamento para uso informativo' not in response.text


def test_regular_public_page_still_uses_selected_language():
    response = client.get('/', cookies={'predibeacon_lang': 'pt-BR'})
    assert response.status_code == 200
    assert response.headers['content-language'] == 'pt-BR'
    assert 'x-predibeacon-language-fallback' not in response.headers
