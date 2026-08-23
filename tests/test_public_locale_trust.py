from app.services.public_locale_trust import translate_trust_page


def test_portuguese_methodology_translates_controlled_content():
    source = "Methodology — PrediBeacon Editorial briefs Risk disclosure >Methodology< PrediBeacon is an independent information service. It does not execute trades, accept deposits, hold customer funds or guarantee outcomes. Market data Freshness Ranking Contract comparison Evidence AI-assisted content Commercial independence Similar titles are not sufficient to establish that two contracts are equivalent. Question wording, deadline, resolution source and complete rules must align. When evidence is incomplete, PrediBeacon fails closed."
    out = translate_trust_page('/methodology', source, 'pt-BR')
    for phrase in ('Metodologia — PrediBeacon', 'Resumos editoriais', 'Divulgação de riscos', 'Dados de mercado', 'Atualização dos dados', 'Classificação', 'Comparação de contratos', 'Conteúdo assistido por IA', 'Independência comercial', 'A PrediBeacon é um serviço independente de informação.', 'Títulos semelhantes não são suficientes'):
        assert phrase in out


def test_spanish_risk_translates_controlled_warning_and_headings():
    source = "Risk disclosure — PrediBeacon >Risk disclosure< Terms Prediction-market activity can result in the loss of the entire amount committed. PrediBeacon provides information, not financial, investment, legal, tax or gambling advice. Prices are not certainties Contract risk Venue and jurisdiction risk Operational risk Conflicts and compensation Responsible use"
    out = translate_trust_page('/risk', source, 'es')
    for phrase in ('Divulgación de riesgos — PrediBeacon', 'Términos', 'La actividad en mercados de predicción puede resultar en la pérdida', 'Los precios no son certezas', 'Riesgo del contrato', 'Riesgo de plataforma y jurisdicción', 'Riesgo operativo', 'Uso responsable'):
        assert phrase in out


def test_additional_languages_translate_labels_but_preserve_uncontrolled_legal_body_in_english():
    body = "PrediBeacon does not accept or safeguard user money, create venue accounts, place orders or settle contracts."
    for locale, label in (
        ('fr', 'Méthodologie'), ('de', 'Methodik'), ('it', 'Metodologia'),
        ('ja', '方法論'), ('ko', '방법론'), ('zh-CN', '方法论'), ('ar', 'المنهجية'),
    ):
        source = f"Methodology {body}"
        out = translate_trust_page('/methodology', source, locale)
        assert label in out
        assert body in out


def test_english_and_non_trust_paths_are_unchanged():
    source = "Methodology Risk disclosure Privacy Terms"
    assert translate_trust_page('/methodology', source, 'en') == source
    assert translate_trust_page('/admin', source, 'pt-BR') == source
