from __future__ import annotations

from urllib.parse import quote

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = (
    "en",
    "es",
    "pt-BR",
    "fr",
    "de",
    "it",
    "ja",
    "ko",
    "zh-CN",
    "ar",
)

LOCALE_LABELS = {
    "en": "English",
    "es": "Español",
    "pt-BR": "Português",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "ja": "日本語",
    "ko": "한국어",
    "zh-CN": "简体中文",
    "ar": "العربية",
}

LOCALE_SHORT = {
    "en": "EN",
    "es": "ES",
    "pt-BR": "PT",
    "fr": "FR",
    "de": "DE",
    "it": "IT",
    "ja": "JA",
    "ko": "KO",
    "zh-CN": "ZH",
    "ar": "AR",
}

PUBLIC_PATHS = {"/", "/top", "/watchlist", "/alerts", "/articles", "/methodology", "/risk", "/privacy", "/terms", "/market"}

PORTUGUESE_TO_ENGLISH = (
    ('<html lang="pt-BR">', '<html lang="en">'),
    ("INTELIGÊNCIA DE MERCADO EM TEMPO REAL", "REAL-TIME MARKET INTELLIGENCE"),
    ("Descubra o que está movimentando os <em>mercados de previsão.</em>", "Discover what is moving <em>prediction markets.</em>"),
    ("Kalshi + Polymarket, priorizados, comparados e explicados em um só lugar.", "Kalshi + Polymarket, prioritized, compared and explained in one place."),
    ("✓ Independente", "✓ Independent"), ("✓ Transparente", "✓ Transparent"), ("◎ Focado no que importa", "◎ Focused on what matters"),
    ("Escolha uma visão", "Choose a view"), ("Clique em Kalshi, PrediBeacon ou Polymarket para explorar.", "Click Kalshi, PrediBeacon or Polymarket to explore."),
    ("mercados monitorados", "markets monitored"), ("Explorar Kalshi →", "Explore Kalshi →"), ("Explorar Polymarket →", "Explore Polymarket →"),
    ("Visão completa do mercado", "Complete market view"), ("Ver visão completa →", "View complete market view →"),
    ("Para você", "For you"), ("Em movimento", "Moving"), ("Mais ativos", "Most active"), ("Terminando em breve", "Closing soon"),
    ("O que está mudando", "What is changing"), ("Dados atuais", "Current data"), ("Carregando movimentos…", "Loading movers…"),
    ("Carregando atividade…", "Loading activity…"), ("Verificando divergências…", "Checking disagreements…"),
    ("● Atualizado há pouco", "● Updated recently"), ("● Verificar atualização", "● Check freshness"), ("Status indisponível", "Status unavailable"),
    ("Nenhum mercado com prazo conhecido está fechando em breve.", "No market with a known deadline is closing soon."),
    ("O ranking por prazo está temporariamente indisponível.", "Closing-soon ranking is temporarily unavailable."),
    ("Indisponível", "Unavailable"), ("Inteligência", "Intelligence"), ("Alertas", "Alerts"), ("Metodologia", "Methodology"),
    ("Resumos", "Insights"), ("Lista de observação", "Watchlist"),
    ("Detalhes do mercado — PrediBeacon", "Market details — PrediBeacon"), ("Carregando inteligência do mercado…", "Loading market intelligence…"),
    ("SINAL ATUAL DO MERCADO", "CURRENT MARKET SIGNAL"), ("Relevância", "Trend score"), ("Volume informado", "Reported volume"),
    ("Tempo restante", "Time remaining"), ("Última observação", "Last observed"), ("Abrir plataforma ↗", "Open platform ↗"),
    ("Adicionar à lista de observação", "Add to watchlist"), ("Remover da lista de observação", "Remove from watchlist"),
    ("Criar alerta", "Create alert"), ("Copiar link do mercado", "Copy market link"), ("Copiar código de incorporação", "Copy embed code"),
    ("A PrediBeacon fornece inteligência e direcionamento. As operações acontecem somente na plataforma externa.", "PrediBeacon provides intelligence and routing. Trades occur only on the external platform."),
    ("QUALIDADE DO MERCADO", "MARKET QUALITY"), ("Qual é a qualidade do sinal exibido?", "How reliable is the displayed signal?"),
    ("Calculando…", "Calculating…"), ("Verificando completude, atualização e histórico utilizável…", "Checking completeness, recency and usable history…"),
    ("VERIFICAÇÃO ENTRE PLATAFORMAS", "CROSS-PLATFORM CHECK"), ("O mesmo contrato está disponível na outra plataforma?", "Is the same contract available elsewhere?"),
    ("Verificando Kalshi e Polymarket…", "Checking Kalshi and Polymarket…"), ("POR QUE IMPORTA", "WHY IT MATTERS"),
    ("O que merece sua atenção", "What deserves your attention"), ("Histórico de probabilidade", "Probability history"),
    ("Linha do tempo do mercado", "Market timeline"), ("Mercados relacionados", "Related markets"), ("← Voltar aos mercados", "← Back to markets"),
    ("← Mercados", "← Markets"), ("Alertas de mercado — PrediBeacon", "Market alerts — PrediBeacon"), ("ACOMPANHE O QUE IMPORTA", "FOLLOW WHAT MATTERS"),
    ("Alertas de mercado", "Market alerts"), ("Criar um alerta", "Create an alert"), ("Alertas salvos", "Saved alerts"),
    ("Carregando mercados…", "Loading markets…"), ("Escolher mercado", "Choose market"), ("Limite de probabilidade", "Probability threshold"),
    ("Receba uma notificação no navegador enquanto a PrediBeacon estiver aberta quando um mercado acompanhado atingir seu limite de probabilidade. As preferências ficam neste navegador.", "Get a browser notification while PrediBeacon is open when a market you follow reaches your probability threshold. Preferences stay in this browser."),
    ("Escolha um mercado primeiro.", "Choose a market first."), ("Alerta salvo para ", "Alert saved for "), ("Probabilidade atual indisponível", "Current probability unavailable"),
    ("Probabilidade indisponível", "Probability unavailable"), ("Este mercado está temporariamente indisponível. A PrediBeacon não substituirá por outro contrato.", "This market is temporarily unavailable. PrediBeacon will not substitute a different contract."),
)

TRANSLATIONS = {
    "pt-BR": {
        "Markets": "Mercados", "Intelligence": "Inteligência", "Watchlist": "Lista de observação", "Alerts": "Alertas", "Insights": "Resumos", "Methodology": "Metodologia",
        "REAL-TIME MARKET INTELLIGENCE": "INTELIGÊNCIA DE MERCADO EM TEMPO REAL", "Discover what is moving <em>prediction markets.</em>": "Descubra o que está movimentando os <em>mercados de previsão.</em>",
        "Kalshi + Polymarket, prioritized, compared and explained in one place.": "Kalshi + Polymarket, priorizados, comparados e explicados em um só lugar.",
        "✓ Independent": "✓ Independente", "✓ Transparent": "✓ Transparente", "◎ Focused on what matters": "◎ Focado no que importa", "Choose a view": "Escolha uma visão",
        "Click Kalshi, PrediBeacon or Polymarket to explore.": "Clique em Kalshi, PrediBeacon ou Polymarket para explorar.", "markets monitored": "mercados monitorados",
        "Explore Kalshi →": "Explorar Kalshi →", "Explore Polymarket →": "Explorar Polymarket →", "Complete market view": "Visão completa do mercado", "View complete market view →": "Ver visão completa →",
        "For you": "Para você", "Moving": "Em movimento", "Most active": "Mais ativos", "Closing soon": "Terminando em breve", "What is changing": "O que está mudando", "Current data": "Dados atuais",
        "Market details — PrediBeacon": "Detalhes do mercado — PrediBeacon", "Loading market intelligence…": "Carregando inteligência do mercado…", "CURRENT MARKET SIGNAL": "SINAL ATUAL DO MERCADO",
        "Trend score": "Relevância", "Reported volume": "Volume informado", "Time remaining": "Tempo restante", "Last observed": "Última observação", "Open platform ↗": "Abrir plataforma ↗",
        "Add to watchlist": "Adicionar à lista de observação", "Remove from watchlist": "Remover da lista de observação", "Create alert": "Criar alerta", "Copy market link": "Copiar link do mercado", "Copy embed code": "Copiar código de incorporação",
        "MARKET QUALITY": "QUALIDADE DO MERCADO", "How reliable is the displayed signal?": "Qual é a qualidade do sinal exibido?", "CROSS-PLATFORM CHECK": "VERIFICAÇÃO ENTRE PLATAFORMAS", "Is the same contract available elsewhere?": "O mesmo contrato está disponível na outra plataforma?", "WHY IT MATTERS": "POR QUE IMPORTA", "What deserves your attention": "O que merece sua atenção", "Probability history": "Histórico de probabilidade", "Market timeline": "Linha do tempo do mercado", "Related markets": "Mercados relacionados",
        "Market alerts — PrediBeacon": "Alertas de mercado — PrediBeacon", "FOLLOW WHAT MATTERS": "ACOMPANHE O QUE IMPORTA", "Market alerts": "Alertas de mercado", "Get a browser notification while PrediBeacon is open when a market you follow reaches your probability threshold. Preferences stay in this browser.": "Receba uma notificação no navegador enquanto a PrediBeacon estiver aberta quando um mercado acompanhado atingir seu limite de probabilidade. As preferências ficam neste navegador.",
        "Create an alert": "Criar um alerta", "Saved alerts": "Alertas salvos", "Choose market": "Escolher mercado", "Probability threshold": "Limite de probabilidade", "Choose a market first.": "Escolha um mercado primeiro.", "Alert saved for ": "Alerta salvo para ", "Current probability unavailable": "Probabilidade atual indisponível", "Probability unavailable": "Probabilidade indisponível", "This market is temporarily unavailable. PrediBeacon will not substitute a different contract.": "Este mercado está temporariamente indisponível. A PrediBeacon não substituirá por outro contrato.", "← Back to markets": "← Voltar aos mercados", "← Markets": "← Mercados",
    },
    "es": {
        "Markets": "Mercados", "Intelligence": "Inteligencia", "Watchlist": "Lista de seguimiento", "Alerts": "Alertas", "Insights": "Resúmenes", "Methodology": "Metodología", "REAL-TIME MARKET INTELLIGENCE": "INTELIGENCIA DE MERCADO EN TIEMPO REAL", "Discover what is moving <em>prediction markets.</em>": "Descubre qué está moviendo los <em>mercados de predicción.</em>", "Kalshi + Polymarket, prioritized, compared and explained in one place.": "Kalshi + Polymarket, priorizados, comparados y explicados en un solo lugar.", "✓ Independent": "✓ Independiente", "✓ Transparent": "✓ Transparente", "◎ Focused on what matters": "◎ Enfocado en lo que importa", "Choose a view": "Elige una vista", "Click Kalshi, PrediBeacon or Polymarket to explore.": "Haz clic en Kalshi, PrediBeacon o Polymarket para explorar.", "markets monitored": "mercados monitoreados", "Explore Kalshi →": "Explorar Kalshi →", "Explore Polymarket →": "Explorar Polymarket →", "Complete market view": "Vista completa del mercado", "View complete market view →": "Ver vista completa →", "For you": "Para ti", "Moving": "En movimiento", "Most active": "Más activos", "Closing soon": "Cierran pronto", "What is changing": "Qué está cambiando", "Current data": "Datos actuales", "Market details — PrediBeacon": "Detalles del mercado — PrediBeacon", "CURRENT MARKET SIGNAL": "SEÑAL ACTUAL DEL MERCADO", "Trend score": "Relevancia", "Reported volume": "Volumen informado", "Time remaining": "Tiempo restante", "Last observed": "Última observación", "Open platform ↗": "Abrir plataforma ↗", "Add to watchlist": "Añadir a seguimiento", "Remove from watchlist": "Quitar de seguimiento", "Create alert": "Crear alerta", "MARKET QUALITY": "CALIDAD DEL MERCADO", "CROSS-PLATFORM CHECK": "VERIFICACIÓN ENTRE PLATAFORMAS", "WHY IT MATTERS": "POR QUÉ IMPORTA", "Probability history": "Historial de probabilidad", "Market timeline": "Cronología del mercado", "Related markets": "Mercados relacionados", "Market alerts": "Alertas de mercado", "Create an alert": "Crear una alerta", "Saved alerts": "Alertas guardadas", "← Back to markets": "← Volver a los mercados", "← Markets": "← Mercados",
    },
    "fr": {"Markets": "Marchés", "Watchlist": "Liste de suivi", "Alerts": "Alertes", "Insights": "Analyses", "Methodology": "Méthodologie", "Choose a view": "Choisir une vue", "For you": "Pour vous", "Moving": "En mouvement", "Most active": "Plus actifs", "Closing soon": "Bientôt clôturés", "Explore Kalshi →": "Explorer Kalshi →", "Explore Polymarket →": "Explorer Polymarket →", "Complete market view": "Vue complète du marché", "Create alert": "Créer une alerte", "Related markets": "Marchés associés"},
    "de": {"Markets": "Märkte", "Watchlist": "Beobachtungsliste", "Alerts": "Alarme", "Insights": "Analysen", "Methodology": "Methodik", "Choose a view": "Ansicht wählen", "For you": "Für dich", "Moving": "In Bewegung", "Most active": "Am aktivsten", "Closing soon": "Endet bald", "Explore Kalshi →": "Kalshi erkunden →", "Explore Polymarket →": "Polymarket erkunden →", "Complete market view": "Vollständige Marktansicht", "Create alert": "Alarm erstellen", "Related markets": "Verwandte Märkte"},
    "it": {"Markets": "Mercati", "Watchlist": "Lista osservati", "Alerts": "Avvisi", "Insights": "Analisi", "Methodology": "Metodologia", "Choose a view": "Scegli una vista", "For you": "Per te", "Moving": "In movimento", "Most active": "Più attivi", "Closing soon": "In chiusura", "Explore Kalshi →": "Esplora Kalshi →", "Explore Polymarket →": "Esplora Polymarket →", "Complete market view": "Vista completa del mercato", "Create alert": "Crea avviso", "Related markets": "Mercati correlati"},
    "ja": {"Markets": "マーケット", "Intelligence": "インテリジェンス", "Watchlist": "ウォッチリスト", "Alerts": "アラート", "Insights": "分析", "Methodology": "方法論", "Choose a view": "表示を選択", "For you": "おすすめ", "Moving": "変動中", "Most active": "最も活発", "Closing soon": "まもなく終了", "Explore Kalshi →": "Kalshiを見る →", "Explore Polymarket →": "Polymarketを見る →", "Complete market view": "市場全体ビュー", "Create alert": "アラートを作成", "Related markets": "関連マーケット"},
    "ko": {"Markets": "마켓", "Intelligence": "인텔리전스", "Watchlist": "관심 목록", "Alerts": "알림", "Insights": "분석", "Methodology": "방법론", "Choose a view": "보기 선택", "For you": "추천", "Moving": "변동 중", "Most active": "가장 활발", "Closing soon": "곧 종료", "Explore Kalshi →": "Kalshi 보기 →", "Explore Polymarket →": "Polymarket 보기 →", "Complete market view": "전체 시장 보기", "Create alert": "알림 만들기", "Related markets": "관련 마켓"},
    "zh-CN": {"Markets": "市场", "Intelligence": "智能分析", "Watchlist": "关注列表", "Alerts": "提醒", "Insights": "分析", "Methodology": "方法论", "Choose a view": "选择视图", "For you": "为你推荐", "Moving": "正在波动", "Most active": "最活跃", "Closing soon": "即将结束", "Explore Kalshi →": "查看 Kalshi →", "Explore Polymarket →": "查看 Polymarket →", "Complete market view": "完整市场视图", "Create alert": "创建提醒", "Related markets": "相关市场"},
    "ar": {"Markets": "الأسواق", "Intelligence": "التحليلات", "Watchlist": "قائمة المتابعة", "Alerts": "التنبيهات", "Insights": "الرؤى", "Methodology": "المنهجية", "Choose a view": "اختر طريقة العرض", "For you": "لك", "Moving": "يتحرك", "Most active": "الأكثر نشاطًا", "Closing soon": "يغلق قريبًا", "Explore Kalshi →": "استكشف Kalshi ←", "Explore Polymarket →": "استكشف Polymarket ←", "Complete market view": "عرض السوق الكامل", "Create alert": "إنشاء تنبيه", "Related markets": "أسواق ذات صلة"},
}

LANGUAGE_CSS = """
.pb-lang{position:relative;margin-left:auto;font-size:.82rem;z-index:40}.pb-lang summary{list-style:none;cursor:pointer;border:1px solid var(--line,#273244);border-radius:999px;padding:.5rem .72rem;font-weight:850;background:var(--panel,#111827);white-space:nowrap}.pb-lang summary::-webkit-details-marker{display:none}.pb-lang-menu{position:absolute;right:0;top:calc(100% + .45rem);min-width:190px;max-height:360px;overflow:auto;border:1px solid var(--line,#273244);border-radius:12px;background:var(--panel,#111827);padding:.4rem;box-shadow:0 14px 40px rgba(0,0,0,.35)}.pb-lang-menu a{display:block;padding:.58rem .7rem;border-radius:8px;text-decoration:none;color:var(--text,#f8fafc)}.pb-lang-menu a:hover,.pb-lang-menu a[aria-current=true]{background:rgba(139,233,199,.08);color:var(--accent,#8be9c7)}[dir=rtl] .pb-lang-menu{right:auto;left:0}@media(max-width:700px){.pb-lang{margin-left:0}.pb-lang-menu{right:auto;left:0}}
"""


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    candidate = value.strip()
    aliases = {"pt": "pt-BR", "pt-br": "pt-BR", "zh": "zh-CN", "zh-cn": "zh-CN"}
    candidate = aliases.get(candidate.casefold(), candidate)
    return candidate if candidate in SUPPORTED_LOCALES else DEFAULT_LOCALE


def _is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith('/markets/') or path.startswith('/articles/') or path.startswith('/creator/')


def _normalize_to_english(html: str) -> str:
    result = html
    for source, target in PORTUGUESE_TO_ENGLISH:
        result = result.replace(source, target)
    return result.replace(">Briefs<", ">Insights<")


def _translate(result: str, locale: str) -> str:
    for source, target in TRANSLATIONS.get(locale, {}).items():
        result = result.replace(source, target)
    return result


def _selector(locale: str, current_path: str) -> str:
    next_value = quote(current_path if current_path.startswith("/") else "/", safe="/?=&%:-")
    links = "".join(f'<a href="/set-language?lang={quote(code)}&next={next_value}" aria-current="{str(code == locale).lower()}">{LOCALE_LABELS[code]}</a>' for code in SUPPORTED_LOCALES)
    return '<details class="pb-lang">' + f'<summary aria-label="Language">🌐 {LOCALE_SHORT[locale]}</summary><div class="pb-lang-menu">{links}</div></details>'


def localize_public_html(path: str, html: str, locale: str = DEFAULT_LOCALE) -> str:
    if not _is_public_path(path):
        return html
    locale = normalize_locale(locale)
    result = _normalize_to_english(html)
    result = result.replace('<html lang="en">', f'<html lang="{locale}"' + (' dir="rtl">' if locale == 'ar' else '>'), 1)
    if locale != DEFAULT_LOCALE:
        result = _translate(result, locale)
    if LANGUAGE_CSS not in result:
        if "</style>" in result:
            result = result.replace("</style>", LANGUAGE_CSS + "</style>", 1)
        elif "</head>" in result:
            result = result.replace("</head>", f"<style>{LANGUAGE_CSS}</style></head>", 1)
    selector = _selector(locale, path)
    if 'class="pb-lang"' not in result:
        if "</nav>" in result:
            result = result.replace("</nav>", selector + "</nav>", 1)
        elif "</header>" in result:
            result = result.replace("</header>", selector + "</header>", 1)
        elif "<body>" in result:
            result = result.replace("<body>", "<body>" + selector, 1)
    return result
