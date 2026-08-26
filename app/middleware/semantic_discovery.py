from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.services.discovery_semantics import SEMANTIC_DISCOVERY_VERSION


_SEMANTIC_SCRIPT = r'''<script data-predibeacon-semantic-discovery="semantic-discovery-v1">
(() => {
  const language = () => (document.documentElement.lang || 'en').toLowerCase();
  const phrases = {
    en: {sharp_move_with_activity:'Sharp probability movement is backed by material reported activity.',closing_soon:'This materially active contract closes within 72 hours, increasing decision urgency.',high_activity:'High reported activity makes this market worth monitoring.',meaningful_move:'A meaningful probability movement is supported by reported market activity.',high_relevance:'PrediBeacon ranks this as a high-relevance market right now.',balanced_signal:'Movement, material activity, freshness and availability make this market relevant now.',empty:"No market currently meets PrediBeacon's documented attention criteria for these filters."},
    'pt-br': {sharp_move_with_activity:'Um movimento forte de probabilidade é sustentado por atividade informada material.',closing_soon:'Este contrato com atividade material fecha em até 72 horas, aumentando a urgência da decisão.',high_activity:'A alta atividade informada faz este mercado merecer acompanhamento.',meaningful_move:'Um movimento relevante de probabilidade é sustentado pela atividade informada do mercado.',high_relevance:'A PrediBeacon classifica este mercado como de alta relevância neste momento.',balanced_signal:'Movimento, atividade material, atualização e disponibilidade tornam este mercado relevante agora.',empty:'Nenhum mercado atende agora aos critérios documentados de atenção da PrediBeacon para estes filtros.'},
    es: {sharp_move_with_activity:'Un movimiento fuerte de probabilidad está respaldado por actividad informada material.',closing_soon:'Este contrato con actividad material cierra en 72 horas, aumentando la urgencia.',high_activity:'La alta actividad informada hace que este mercado merezca seguimiento.',meaningful_move:'Un movimiento relevante de probabilidad está respaldado por la actividad informada.',high_relevance:'PrediBeacon clasifica este mercado como de alta relevancia ahora.',balanced_signal:'Movimiento, actividad material, actualidad y disponibilidad hacen relevante este mercado.',empty:'Ningún mercado cumple ahora los criterios documentados de atención de PrediBeacon para estos filtros.'},
    fr: {sharp_move_with_activity:'Un fort mouvement de probabilité est soutenu par une activité déclarée significative.',closing_soon:'Ce contrat avec une activité significative clôture sous 72 heures.',high_activity:'Une forte activité déclarée rend ce marché digne de suivi.',meaningful_move:'Un mouvement de probabilité significatif est soutenu par l’activité déclarée.',high_relevance:'PrediBeacon classe actuellement ce marché comme très pertinent.',balanced_signal:'Mouvement, activité significative, fraîcheur et disponibilité rendent ce marché pertinent.',empty:'Aucun marché ne respecte actuellement les critères documentés de PrediBeacon pour ces filtres.'},
    de: {sharp_move_with_activity:'Eine starke Wahrscheinlichkeitsbewegung wird durch materielle gemeldete Aktivität gestützt.',closing_soon:'Dieser materiell aktive Kontrakt schließt innerhalb von 72 Stunden.',high_activity:'Hohe gemeldete Aktivität macht diesen Markt beobachtenswert.',meaningful_move:'Eine relevante Wahrscheinlichkeitsbewegung wird durch gemeldete Aktivität gestützt.',high_relevance:'PrediBeacon stuft diesen Markt derzeit als hoch relevant ein.',balanced_signal:'Bewegung, materielle Aktivität, Aktualität und Verfügbarkeit machen diesen Markt relevant.',empty:'Derzeit erfüllt kein Markt die dokumentierten PrediBeacon-Aufmerksamkeitskriterien für diese Filter.'},
    it: {sharp_move_with_activity:'Un forte movimento di probabilità è sostenuto da attività segnalata materiale.',closing_soon:'Questo contratto con attività materiale chiude entro 72 ore.',high_activity:'L’elevata attività segnalata rende questo mercato degno di attenzione.',meaningful_move:'Un movimento rilevante di probabilità è sostenuto dall’attività segnalata.',high_relevance:'PrediBeacon classifica questo mercato come altamente rilevante ora.',balanced_signal:'Movimento, attività materiale, aggiornamento e disponibilità rendono rilevante questo mercato.',empty:'Nessun mercato soddisfa ora i criteri documentati di attenzione PrediBeacon per questi filtri.'},
    ja: {sharp_move_with_activity:'大きな確率変動が、十分な報告済み市場活動によって裏付けられています。',closing_soon:'十分な活動があるこの契約は72時間以内に終了します。',high_activity:'報告済み活動が多く、注視する価値があります。',meaningful_move:'意味のある確率変動が報告済み市場活動に支えられています。',high_relevance:'PrediBeaconは現在この市場を高関連度と評価しています。',balanced_signal:'変動、十分な活動、鮮度、利用可能性により現在注目に値します。',empty:'現在、このフィルターでPrediBeaconの文書化された注目基準を満たす市場はありません。'},
    ko: {sharp_move_with_activity:'큰 확률 변동이 충분한 보고 활동으로 뒷받침됩니다.',closing_soon:'충분한 활동이 있는 이 계약은 72시간 이내에 마감됩니다.',high_activity:'높은 보고 활동으로 이 시장은 주목할 가치가 있습니다.',meaningful_move:'의미 있는 확률 변동이 보고된 시장 활동으로 뒷받침됩니다.',high_relevance:'PrediBeacon은 현재 이 시장을 높은 관련성으로 평가합니다.',balanced_signal:'변동, 충분한 활동, 최신성 및 가용성으로 현재 관련성이 있습니다.',empty:'현재 이 필터에서 PrediBeacon의 문서화된 주목 기준을 충족하는 시장이 없습니다.'},
    'zh-cn': {sharp_move_with_activity:'明显的概率变动得到实质性已报告市场活动的支持。',closing_soon:'这个具有实质性活动的合约将在72小时内结束。',high_activity:'较高的已报告活动使该市场值得关注。',meaningful_move:'有意义的概率变动得到已报告市场活动的支持。',high_relevance:'PrediBeacon目前将该市场评为高相关性。',balanced_signal:'变动、实质性活动、时效性和可用性使该市场目前值得关注。',empty:'当前没有市场满足 PrediBeacon 针对这些筛选条件记录的关注标准。'},
    ar: {sharp_move_with_activity:'تدعم الحركة القوية في الاحتمال نشاطات سوق مُبلغ عنها ذات أهمية.',closing_soon:'يغلق هذا العقد ذو النشاط المادي خلال 72 ساعة.',high_activity:'يجعل النشاط المرتفع المُبلغ عنه هذا السوق جديراً بالمتابعة.',meaningful_move:'تدعم حركة احتمال ذات معنى نشاطات السوق المُبلغ عنها.',high_relevance:'تصنف PrediBeacon هذا السوق حالياً على أنه عالي الصلة.',balanced_signal:'تجعل الحركة والنشاط المادي والحداثة والتوافر هذا السوق ذا صلة الآن.',empty:'لا يوجد سوق يحقق حالياً معايير الاهتمام الموثقة لدى PrediBeacon لهذه المرشحات.'}
  };
  const dictionary = () => phrases[language()] || phrases.en;
  window.why = function(m) { const code=m&&m.attention_reason_code; return dictionary()[code] || dictionary().balanced_signal; };
  const rewriteEmptyState = () => {
    const state=document.querySelector('#state'), count=document.querySelector('#count');
    if(!state||!count)return;
    const zero=/^0\s/.test((count.textContent||'').trim()), target=dictionary().empty;
    if(zero&&!state.hidden&&state.textContent!==target)state.textContent=target;
  };
  const state=document.querySelector('#state'), count=document.querySelector('#count');
  if(state)new MutationObserver(rewriteEmptyState).observe(state,{childList:true,subtree:true,characterData:true,attributes:true});
  if(count)new MutationObserver(rewriteEmptyState).observe(count,{childList:true,subtree:true,characterData:true});
  queueMicrotask(rewriteEmptyState);
})();
</script>'''


def register_semantic_discovery_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def semantic_discovery_surface(request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        is_surface = request.url.path in {"/", "/top"} and response.status_code == 200 and "text/html" in content_type
        if not is_surface:
            return response
        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8") for chunk in chunks)
        text = raw.decode("utf-8", errors="replace")
        # Public intelligence surfaces consume curated Discovery, while the
        # monitored inventory contract remains available at /api/v1/markets.
        text = text.replace("/api/v1/markets?", "/api/v1/discovery?")
        if 'data-predibeacon-semantic-discovery="semantic-discovery-v1"' not in text:
            text = text.replace("</body>", _SEMANTIC_SCRIPT + "</body>")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["X-PrediBeacon-Semantic-Discovery"] = SEMANTIC_DISCOVERY_VERSION
        return Response(text, status_code=response.status_code, headers=headers, media_type="text/html")
