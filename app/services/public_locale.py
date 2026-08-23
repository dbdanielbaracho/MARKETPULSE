from __future__ import annotations


COMMON = (
    ('<html lang="en">', '<html lang="pt-BR">'),
    ('Intelligence', 'Inteligência'),
    ('← Back to markets', '← Voltar aos mercados'),
    ('← Markets', '← Mercados'),
)

MARKET = (
    ('Market details — PrediBeacon', 'Detalhes do mercado — PrediBeacon'),
    ('Loading market intelligence…', 'Carregando inteligência do mercado…'),
    ('CURRENT MARKET SIGNAL', 'SINAL ATUAL DO MERCADO'),
    ('Trend score', 'Relevância'),
    ('Reported volume', 'Volume informado'),
    ('Time remaining', 'Tempo restante'),
    ('Last observed', 'Última observação'),
    ('Open platform ↗', 'Abrir plataforma ↗'),
    ('Add to watchlist', 'Adicionar à lista de observação'),
    ('Create alert', 'Criar alerta'),
    ('Copy market link', 'Copiar link do mercado'),
    ('Copy embed code', 'Copiar código de incorporação'),
    ('PrediBeacon provides intelligence and routing. Trades occur only on the external platform.', 'A PrediBeacon fornece inteligência e direcionamento. As operações acontecem somente na plataforma externa.'),
    ('MARKET QUALITY', 'QUALIDADE DO MERCADO'),
    ('How reliable is the displayed signal?', 'Qual é a qualidade do sinal exibido?'),
    ('Calculating…', 'Calculando…'),
    ('Checking completeness, recency and usable history…', 'Verificando completude, atualização e histórico utilizável…'),
    ('Market Quality measures data completeness and signal reliability. It is not outcome confidence and does not predict whether YES or NO will win.', 'Qualidade do Mercado mede completude dos dados e confiabilidade do sinal. Não representa confiança no resultado e não prevê se SIM ou NÃO vencerá.'),
    ('CROSS-PLATFORM CHECK', 'VERIFICAÇÃO ENTRE PLATAFORMAS'),
    ('Is the same contract available elsewhere?', 'O mesmo contrato está disponível na outra plataforma?'),
    ('Checking Kalshi and Polymarket…', 'Verificando Kalshi e Polymarket…'),
    ('WHY IT MATTERS', 'POR QUE IMPORTA'),
    ('What deserves your attention', 'O que merece sua atenção'),
    ('Loading market signals…', 'Carregando sinais do mercado…'),
    ('Probability history', 'Histórico de probabilidade'),
    ('aria-label="Probability history"', 'aria-label="Histórico de probabilidade"'),
    ('Loading history…', 'Carregando histórico…'),
    ('Market timeline', 'Linha do tempo do mercado'),
    ('Loading timeline…', 'Carregando linha do tempo…'),
    ('Related markets', 'Mercados relacionados'),
    ('Related does not mean equivalent. PrediBeacon labels equivalence separately.', 'Relacionado não significa equivalente. A PrediBeacon identifica equivalência separadamente.'),
    ('Loading related markets…', 'Carregando mercados relacionados…'),
    ("'Remove from watchlist'", "'Remover da lista de observação'"),
    ("'Add to watchlist'", "'Adicionar à lista de observação'"),
    ("?'Unavailable'", "?'Indisponível'"),
    ("return'Not published'", "return'Não informado'"),
    ("return'Closed'", "return'Encerrado'"),
    ("return'Unknown'", "return'Desconhecido'"),
    ("return'Just now'", "return'Agora mesmo'"),
    ("+'m ago'", "+' min atrás'"),
    ("+'h ago'", "+' h atrás'"),
    ("'Strong data completeness and recent history.'", "'Boa completude de dados e histórico recente.'"),
    ("'Usable signal, with some data limitations.'", "'Sinal utilizável, com algumas limitações de dados.'"),
    ("'Limited signal quality; interpret the displayed probability with extra caution.'", "'Qualidade de sinal limitada; interprete a probabilidade exibida com cautela adicional.'"),
    ("'Market identifier is missing.'", "'Identificador do mercado ausente.'"),
    ("'Probability unavailable'", "'Probabilidade indisponível'"),
    ("'A reliable recent probability change is not available yet.'", "'Ainda não há uma variação recente de probabilidade confiável disponível.'"),
    ("'▲ Rising '", "'▲ Subindo '"),
    ("'▼ Falling '", "'▼ Caindo '"),
    ("+' percentage points in the latest comparison window.'", "+' pontos percentuais na janela de comparação mais recente.'"),
    ("'Open on '", "'Abrir na '"),
    ("'This market is temporarily unavailable. PrediBeacon will not substitute a different contract.'", "'Este mercado está temporariamente indisponível. A PrediBeacon não substituirá por outro contrato.'"),
    ("'Market link copied'", "'Link do mercado copiado'"),
    ("'Unable to copy link'", "'Não foi possível copiar o link'"),
    ("'Embed code copied'", "'Código de incorporação copiado'"),
    ("'Unable to copy embed'", "'Não foi possível copiar o código'"),
    ("'Signal explanation is temporarily unavailable.'", "'A explicação do sinal está temporariamente indisponível.'"),
    ("'More observations are needed for this period.'", "'São necessárias mais observações para este período.'"),
    ("+' observations · '", "+' observações · '"),
    ("'History is temporarily unavailable.'", "'O histórico está temporariamente indisponível.'"),
    ("'No same-question candidate is present on the other current venue feed.'", "'Não há candidato para a mesma pergunta no feed atual da outra plataforma.'"),
    ("'No breaking acceleration above the 3-point threshold is visible in the recent 6-hour history window.'", "'Nenhuma aceleração acima do limite de 3 pontos aparece na janela recente de 6 horas.'"),
)

ALERTS = (
    ('Market alerts — PrediBeacon', 'Alertas de mercado — PrediBeacon'),
    ('FOLLOW WHAT MATTERS', 'ACOMPANHE O QUE IMPORTA'),
    ('Market alerts', 'Alertas de mercado'),
    ('Get a browser notification while PrediBeacon is open when a market you follow reaches your probability threshold. Preferences stay in this browser.', 'Receba uma notificação no navegador enquanto a PrediBeacon estiver aberta quando um mercado acompanhado atingir seu limite de probabilidade. As preferências ficam neste navegador.'),
    ('Create an alert', 'Criar um alerta'),
    ('aria-label="Choose market"', 'aria-label="Escolher mercado"'),
    ('Loading markets…', 'Carregando mercados…'),
    ('aria-label="Probability threshold"', 'aria-label="Limite de probabilidade"'),
    ('Create alert', 'Criar alerta'),
    ('Saved alerts', 'Alertas salvos'),
    ('Choose a market from a market page or Watchlist', 'Escolha um mercado a partir de uma página de mercado ou da Lista de observação'),
    ('No market has been selected yet.', 'Nenhum mercado foi selecionado ainda.'),
    ('Open a market', 'Abra um mercado'),
    ('and use “Create alert”, or add it to your Watchlist.', 'e use “Criar alerta”, ou adicione-o à sua Lista de observação.'),
    ("'Choose a market first.'", "'Escolha um mercado primeiro.'"),
    ("'Choose a probability threshold from 1% to 99%.'", "'Escolha um limite de probabilidade entre 1% e 99%.'"),
    ("'That market is no longer available.'", "'Esse mercado não está mais disponível.'"),
    ("'Alert saved for '", "'Alerta salvo para '"),
    ('No alerts saved yet. Alerts are most useful for markets already in your Watchlist.', 'Nenhum alerta salvo ainda. Alertas são mais úteis para mercados que já estão na sua Lista de observação.'),
    ("'Market no longer available'", "'Mercado não está mais disponível'"),
    ("'UNAVAILABLE'", "'INDISPONÍVEL'"),
    ("'Current probability unavailable'", "'Probabilidade atual indisponível'"),
    ("'Last seen at '", "'Última observação em '"),
    ('Notify at ${x.threshold}% or higher', 'Notificar em ${x.threshold}% ou mais'),
    ('>Remove</button>', '>Remover</button>'),
    ("'PrediBeacon market alert'", "'Alerta de mercado PrediBeacon'"),
    ("+' reached '+p+'%'", "+' atingiu '+p+'%'"),
)


def localize_public_html(path: str, html: str) -> str:
    replacements = COMMON
    if path == '/alerts':
        replacements += ALERTS
    elif path == '/market' or path.startswith('/markets/'):
        replacements += MARKET
    else:
        return html
    result = html
    for source, target in replacements:
        result = result.replace(source, target)
    return result
