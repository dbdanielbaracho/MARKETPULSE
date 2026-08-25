from __future__ import annotations


_HOME_STYLE = r'''<style id="predibeacon-home-platform-visibility-style">
.compare-panel{display:none!important}
.discovery-explainer{margin:.7rem 0 1.25rem;padding:.85rem 1rem;border-left:4px solid var(--accent);background:var(--panel);color:var(--muted);line-height:1.55}.discovery-explainer strong{color:var(--text)}
.platform-availability{margin-top:.8rem;border:1px solid var(--line);border-radius:12px;padding:.75rem .85rem;background:rgba(0,0,0,.12);font-size:.84rem;line-height:1.45}.platform-availability strong{display:block;color:var(--text);margin-bottom:.2rem}.platform-availability .muted{color:var(--muted)}.platform-availability .verified-other{color:var(--accent);font-weight:850}.platform-availability .candidate-other{color:#fbbf24;font-weight:800}.platform-availability .single-venue{color:var(--muted);font-weight:750}
</style>'''


_HOME_SCRIPT = r'''<script id="predibeacon-home-platform-visibility-script">
(()=>{
  const checked=new Map();
  const inFlight=new Map();
  const otherVenue=venue=>venue==='kalshi'?'Polymarket':'Kalshi';
  const venueLabel=venue=>venue==='kalshi'?'Kalshi':'Polymarket';
  const probability=v=>v==null?'':` · ${Math.round(Number(v)*100)}% lá`;

  const discoveryHeading=document.querySelector('#markets .section-title h2');
  if(discoveryHeading)discoveryHeading.textContent='Mercados que merecem atenção agora';
  const gapHeading=document.querySelector('#disagreements h3');
  if(gapHeading)gapHeading.textContent='Onde Kalshi e Polymarket mais discordam';

  const sort=document.querySelector('#sort');
  if(sort){
    const labels={trending:'Relevância PrediBeacon',movers:'Maiores movimentos de probabilidade',volume:'Maior volume informado'};
    for(const option of sort.options){if(labels[option.value])option.textContent=labels[option.value]}
    sort.setAttribute('aria-label','Ordenar mercados');
  }
  const venueFilter=document.querySelector('label:has(#venue) .eyebrow');
  if(venueFilter)venueFilter.textContent='PLATAFORMA';
  const venueSelect=document.querySelector('#venue');
  if(venueSelect)venueSelect.setAttribute('aria-label','Filtrar por plataforma');

  if(discoveryHeading&&!document.querySelector('.discovery-explainer')){
    const explainer=document.createElement('p');
    explainer.className='discovery-explainer';
    explainer.innerHTML='<strong>Por que esta ordem?</strong> A relevância PrediBeacon combina movimento observado, atividade informada, proximidade do fechamento, atualização e qualidade dos dados. Cada mercado também informa se o mesmo contrato foi verificado na outra plataforma.';
    discoveryHeading.closest('.section-title')?.insertAdjacentElement('afterend',explainer);
  }

  function ensurePanel(card,id,venue){
    let panel=card.querySelector('.platform-availability');
    if(panel)return panel;
    panel=document.createElement('div');
    panel.className='platform-availability';
    panel.dataset.marketId=id;
    panel.dataset.venue=venue;
    panel.setAttribute('role','status');
    panel.setAttribute('aria-live','polite');
    panel.innerHTML=`<strong>Disponível na ${venueLabel(venue)}</strong><span class="muted">Verificando ${otherVenue(venue)} para o mesmo contrato…</span>`;
    const actions=card.querySelector('.actions');
    if(actions)card.insertBefore(panel,actions);else card.append(panel);
    return panel;
  }

  function render(panel,result,venue){
    const current=venueLabel(venue),other=otherVenue(venue);
    if(!result){
      panel.innerHTML=`<strong>Disponível na ${current}</strong><span class="muted">Verificação entre plataformas temporariamente indisponível.</span>`;
      return;
    }
    const counterpart=result.counterpart;
    const verification=result.verification;
    if(counterpart&&verification?.equivalent_contracts){
      panel.innerHTML=`<strong>Disponível na ${current}</strong><span class="verified-other">Também na ${venueLabel(counterpart.venue)} · equivalente verificado${probability(counterpart.probability)}</span><br><span class="muted">Confiança da verificação ${verification.confidence}/100.</span>`;
      return;
    }
    if(counterpart){
      panel.innerHTML=`<strong>Disponível na ${current}</strong><span class="candidate-other">Mercado semelhante encontrado na ${venueLabel(counterpart.venue)}, mas não foi verificado como o mesmo contrato.</span>`;
      return;
    }
    panel.innerHTML=`<strong>Disponível na ${current}</strong><span class="single-venue">Nenhum equivalente verificado encontrado na ${other}.</span>`;
  }

  async function lookup(id,venue,panel){
    if(checked.has(id)){render(panel,checked.get(id),venue);return}
    if(inFlight.has(id)){render(panel,await inFlight.get(id),venue);return}
    const promise=(async()=>{
      try{
        const r=await fetch('/api/v1/market/cross-platform?'+new URLSearchParams({market_id:id,candidate_limit:'3'}));
        if(!r.ok)throw new Error('indisponivel');
        return await r.json();
      }catch{return null}
    })();
    inFlight.set(id,promise);
    const result=await promise;
    inFlight.delete(id);
    checked.set(id,result);
    render(panel,result,venue);
  }

  const observer='IntersectionObserver'in window?new IntersectionObserver(entries=>{
    for(const entry of entries){
      if(!entry.isIntersecting)continue;
      observer.unobserve(entry.target);
      const panel=entry.target.querySelector('.platform-availability');
      if(panel)lookup(panel.dataset.marketId,panel.dataset.venue,panel);
    }
  },{rootMargin:'320px 0px'}):null;

  function scan(){
    for(const card of document.querySelectorAll('#grid .card')){
      if(card.dataset.crossPlatformVisibility==='ready')continue;
      const watch=card.querySelector('.watch[data-id]');
      const badge=card.querySelector('.venue-badge');
      if(!watch||!badge)continue;
      const id=watch.dataset.id;
      const venue=badge.classList.contains('kalshi')?'kalshi':'polymarket';
      ensurePanel(card,id,venue);
      card.dataset.crossPlatformVisibility='ready';
      if(observer)observer.observe(card);else lookup(id,venue,card.querySelector('.platform-availability'));
    }
  }

  const grid=document.querySelector('#grid');
  if(grid){new MutationObserver(scan).observe(grid,{childList:true});scan()}
})();
</script>'''


# The base homepage originally allowed overlapping discovery fetches to resolve in
# arbitrary order. A slow response from an old filter could therefore overwrite a
# newer user choice. Keep the original render fragment intact enough for the
# fail-closed curation middleware to rewrite it, while making request ownership
# explicit and aborting stale work.
_LOAD_DECLARATION = "let category='';"
_LOAD_DECLARATION_SAFE = "let category='',discoveryLoadSeq=0,discoveryController=null;"
_LOAD_START = "async function load(){state.hidden=false;grid.innerHTML='';"
_LOAD_START_SAFE = (
    "async function load(){const seq=++discoveryLoadSeq;"
    "if(discoveryController)discoveryController.abort();"
    "discoveryController=new AbortController();"
    "const signal=discoveryController.signal;"
    "state.hidden=false;state.className='state';state.textContent='Loading market data…';"
    "count.textContent='Loading…';grid.innerHTML='';"
)
_LOAD_FETCH = "const r=await fetch('/api/v1/markets?'+q);if(!r.ok)throw new Error();const data=await r.json();grid.innerHTML=data.map(card).join('');"
_LOAD_FETCH_SAFE = (
    "const r=await fetch('/api/v1/markets?'+q,{signal});"
    "if(seq!==discoveryLoadSeq)return;"
    "if(!r.ok)throw new Error();"
    "const data=await r.json();"
    "if(seq!==discoveryLoadSeq)return;"
    "grid.innerHTML=data.map(card).join('');"
)
_LOAD_CATCH = "}catch{count.textContent='Unavailable';state.className='error';state.textContent='Market discovery is temporarily unavailable. PrediBeacon will not invent replacement data.'}}"
_LOAD_CATCH_SAFE = (
    "}catch(error){if(seq!==discoveryLoadSeq||error?.name==='AbortError')return;"
    "count.textContent='Unavailable';state.className='error';"
    "state.textContent='Market discovery is temporarily unavailable. PrediBeacon will not invent replacement data.'}}"
)


def _serialize_discovery_loads(html: str) -> str:
    """Make the latest homepage interaction the only response allowed to render."""
    if "discoveryLoadSeq" in html:
        return html
    required = (_LOAD_DECLARATION, _LOAD_START, _LOAD_FETCH, _LOAD_CATCH)
    if not all(fragment in html for fragment in required):
        return html
    out = html.replace(_LOAD_DECLARATION, _LOAD_DECLARATION_SAFE, 1)
    out = out.replace(_LOAD_START, _LOAD_START_SAFE, 1)
    out = out.replace(_LOAD_FETCH, _LOAD_FETCH_SAFE, 1)
    out = out.replace(_LOAD_CATCH, _LOAD_CATCH_SAFE, 1)
    return out


def enhance_home_template(html: str) -> str:
    """Apresenta ranking e disponibilidade de plataformas nativamente em português."""
    enhanced = html.replace('<html lang="en">', '<html lang="pt-BR">', 1)
    enhanced = enhanced.replace('>Briefs</a>', '>Resumos</a>', 1)
    enhanced = _serialize_discovery_loads(enhanced)
    if 'id="predibeacon-home-platform-visibility-script"' in enhanced:
        return enhanced
    if "</head>" in enhanced:
        enhanced = enhanced.replace("</head>", _HOME_STYLE + "</head>", 1)
    if "</body>" in enhanced:
        enhanced = enhanced.replace("</body>", _HOME_SCRIPT + "</body>", 1)
    return enhanced
