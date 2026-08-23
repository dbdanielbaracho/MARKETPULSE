from app.services.public_locale import localize_public_html


def test_missing_translation_falls_back_to_english():
    html = '<html lang="en"><head><style></style></head><body><header></header><p>Contract resolution source</p></body></html>'
    translated = localize_public_html('/', html, 'fr')
    assert 'Contract resolution source' in translated
    assert '<html lang="fr">' in translated
