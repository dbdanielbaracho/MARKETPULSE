from __future__ import annotations


def _apply(html: str, replacements: dict[str, str]) -> str:
    result = html
    # Apply the most specific phrases first so shorter labels cannot corrupt
    # longer dynamic states (for example plural creator counts or error text).
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(source, target)
    return result


ARTICLE_LIST = {
    "pt-BR": {
        "PrediBeacon — Editorial briefs": "PrediBeacon — Resumos editoriais",
        "PREDIBEACON BRIEFS": "RESUMOS PREDIBEACON",
        "Editorial intelligence, with evidence.": "Inteligência editorial, com evidências.",
        "Short explanations of notable prediction-market moves. Briefs are published only after review and retain their attributable sources.": "Explicações curtas sobre movimentos relevantes em mercados de previsão. Os resumos só são publicados após revisão e mantêm suas fontes atribuíveis.",
        ">Top 10<": ">Top 10<", ">Watchlist<": ">Lista de observação<", ">Alerts<": ">Alertas<", ">Methodology<": ">Metodologia<",
        ">Risk<": ">Riscos<", ">Privacy<": ">Privacidade<", ">Terms<": ">Termos<",
        "Prediction market intelligence": "Inteligência de mercados de previsão",
    },
    "es": {
        "PrediBeacon — Editorial briefs": "PrediBeacon — Resúmenes editoriales",
        "PREDIBEACON BRIEFS": "RESÚMENES PREDIBEACON",
        "Editorial intelligence, with evidence.": "Inteligencia editorial, con evidencia.",
        "Short explanations of notable prediction-market moves. Briefs are published only after review and retain their attributable sources.": "Explicaciones breves de movimientos relevantes en mercados de predicción. Los resúmenes se publican solo después de revisión y conservan sus fuentes atribuibles.",
        ">Watchlist<": ">Lista de seguimiento<", ">Alerts<": ">Alertas<", ">Methodology<": ">Metodología<",
        ">Risk<": ">Riesgos<", ">Privacy<": ">Privacidad<", ">Terms<": ">Términos<",
        "Prediction market intelligence": "Inteligencia de mercados de predicción",
    },
}

ARTICLE_DETAIL = {
    "pt-BR": {
        "← All briefs": "← Todos os resumos", "PREDIBEACON BRIEF": "RESUMO PREDIBEACON", ">Sources<": ">Fontes<",
        "Prediction-market prices can change. PrediBeacon provides informational market intelligence and does not guarantee outcomes.": "Os preços dos mercados de previsão podem mudar. A PrediBeacon fornece inteligência informativa de mercado e não garante resultados.",
        ">Methodology<": ">Metodologia<", ">Risk<": ">Riscos<", ">Privacy<": ">Privacidade<",
    },
    "es": {
        "← All briefs": "← Todos los resúmenes", "PREDIBEACON BRIEF": "RESUMEN PREDIBEACON", ">Sources<": ">Fuentes<",
        "Prediction-market prices can change. PrediBeacon provides informational market intelligence and does not guarantee outcomes.": "Los precios de los mercados de predicción pueden cambiar. PrediBeacon ofrece inteligencia informativa de mercado y no garantiza resultados.",
        ">Methodology<": ">Metodología<", ">Risk<": ">Riesgos<", ">Privacy<": ">Privacidad<",
    },
}

CREATOR = {
    "pt-BR": {
        "Creator markets — PrediBeacon": "Mercados do creator — PrediBeacon", "Creator markets": "Mercados do creator",
        "A tracked selection of prediction markets. Creator compensation, when applicable, is based only on reconciled partner revenue.": "Uma seleção acompanhada de mercados de previsão. A remuneração do creator, quando aplicável, é baseada somente em receita de parceiros reconciliada.",
        "Loading…": "Carregando…", "Markets selected by @": "Mercados selecionados por @", "Trend ": "Relevância ",
        "Explore market": "Explorar mercado", " selected market": " mercado selecionado", " selected markets": " mercados selecionados",
        "No active market selections are available.": "Nenhuma seleção ativa de mercado está disponível.",
        "Creator markets are temporarily unavailable.": "Os mercados do creator estão temporariamente indisponíveis.",
    },
    "es": {
        "Creator markets — PrediBeacon": "Mercados del creator — PrediBeacon", "Creator markets": "Mercados del creator",
        "A tracked selection of prediction markets. Creator compensation, when applicable, is based only on reconciled partner revenue.": "Una selección seguida de mercados de predicción. La compensación del creator, cuando corresponde, se basa únicamente en ingresos de socios reconciliados.",
        "Loading…": "Cargando…", "Markets selected by @": "Mercados seleccionados por @", "Trend ": "Relevancia ",
        "Explore market": "Explorar mercado", " selected market": " mercado seleccionado", " selected markets": " mercados seleccionados",
        "No active market selections are available.": "No hay selecciones activas de mercado disponibles.",
        "Creator markets are temporarily unavailable.": "Los mercados del creator no están disponibles temporalmente.",
    },
}

ESSENTIAL = {
    "fr": {"Editorial intelligence, with evidence.": "Intelligence éditoriale, avec des preuves.", "← All briefs": "← Tous les résumés", ">Sources<": ">Sources<", "Creator markets": "Marchés du créateur", "Explore market": "Explorer le marché"},
    "de": {"Editorial intelligence, with evidence.": "Redaktionelle Marktintelligenz mit Belegen.", "← All briefs": "← Alle Zusammenfassungen", ">Sources<": ">Quellen<", "Creator markets": "Creator-Märkte", "Explore market": "Markt erkunden"},
    "it": {"Editorial intelligence, with evidence.": "Intelligence editoriale, con prove.", "← All briefs": "← Tutti i riepiloghi", ">Sources<": ">Fonti<", "Creator markets": "Mercati del creator", "Explore market": "Esplora mercato"},
    "ja": {"Editorial intelligence, with evidence.": "根拠に基づく編集インテリジェンス。", "← All briefs": "← すべての要約", ">Sources<": ">情報源<", "Creator markets": "クリエイターのマーケット", "Explore market": "マーケットを見る"},
    "ko": {"Editorial intelligence, with evidence.": "근거가 있는 편집 인텔리전스.", "← All briefs": "← 모든 요약", ">Sources<": ">출처<", "Creator markets": "크리에이터 마켓", "Explore market": "마켓 탐색"},
    "zh-CN": {"Editorial intelligence, with evidence.": "有依据的编辑市场情报。", "← All briefs": "← 所有摘要", ">Sources<": ">来源<", "Creator markets": "创作者市场", "Explore market": "探索市场"},
    "ar": {"Editorial intelligence, with evidence.": "معلومات تحريرية مدعومة بالأدلة.", "← All briefs": "← جميع الملخصات", ">Sources<": ">المصادر<", "Creator markets": "أسواق المنشئ", "Explore market": "استكشاف السوق"},
}


def translate_content_shell(path: str, html: str, locale: str) -> str:
    if locale == "en":
        return html
    if path == "/articles":
        return _apply(html, ARTICLE_LIST.get(locale, ESSENTIAL.get(locale, {})))
    if path.startswith("/articles/"):
        return _apply(html, ARTICLE_DETAIL.get(locale, ESSENTIAL.get(locale, {})))
    if path.startswith("/creator/"):
        return _apply(html, CREATOR.get(locale, ESSENTIAL.get(locale, {})))
    return html
