from __future__ import annotations

STYLE = r'''<style id="predibeacon-venue-context-style">
.venue-context{display:none;margin:0 auto 1.4rem;border:1px solid var(--line);border-radius:16px;background:var(--panel);padding:1rem 1.1rem}.venue-context[data-visible=true]{display:block}.venue-context-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap}.venue-context-title{margin:0;font-size:1.2rem}.venue-context-sub{color:var(--muted);font-size:.84rem;margin:.25rem 0 0}.venue-context-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem;margin-top:.9rem}.venue-context-stat{border:1px solid var(--line);border-radius:12px;padding:.8rem;min-width:0}.venue-context-stat span{display:block;color:var(--muted);font-size:.74rem;margin-bottom:.3rem}.venue-context-stat strong{display:block;font-size:.9rem;line-height:1.35;overflow-wrap:anywhere}.venue-context-stat em{display:block;color:var(--accent);font-style:normal;font-weight:800;margin-top:.25rem;font-size:.78rem}@media(max-width:850px){.venue-context-grid{grid-template-columns:1fr 1fr}}@media(max-width:520px){.venue-context-grid{grid-template-columns:1fr}}
</style>'''

SCRIPT = r'''<script id="predibeacon-venue-context-script">
(()=>{
 const markets=document.querySelector('#markets');if(!markets)return;
 const locale=(document.documentElement.lang||'en').toLowerCase();
 const catalogs={
   en:{platformView:'Platform view',loading:'Loading current data…',summary:'Summary calculated from the current feed for this platform.',status:'Status',loadingShort:'Loading…',relevant:'Most relevant',probability:'Probability',mover:'Biggest mover',moveUnavailable:'movement unavailable',activity:'Highest activity',reportedVolume:'Reported volume US$',closing:'Closes first',inWord:'In',unknown:'No data available right now',temporarily:'Platform summary is temporarily unavailable.',marketsRemain:'The markets below remain accessible.',closed:'closed',deadlineUnknown:'deadline unknown'},
   'pt-br':{platformView:'Visão da plataforma',loading:'Carregando dados atuais…',summary:'Resumo calculado com os dados atuais do feed desta plataforma.',status:'Status',loadingShort:'Carregando…',relevant:'Mais relevante',probability:'Probabilidade',mover:'Maior movimento',moveUnavailable:'movimento indisponível',activity:'Maior atividade',reportedVolume:'Volume informado US$',closing:'Fecha primeiro',inWord:'Em',unknown:'Nenhum dado disponível agora',temporarily:'Resumo da plataforma temporariamente indisponível.',marketsRemain:'Os mercados abaixo continuam acessíveis.',closed:'fechado',deadlineUnknown:'prazo desconhecido'},
   es:{platformView:'Vista de la plataforma',loading:'Cargando datos actuales…',summary:'Resumen calculado con los datos actuales del feed de esta plataforma.',status:'Estado',loadingShort:'Cargando…',relevant:'Más relevante',probability:'Probabilidad',mover:'Mayor movimiento',moveUnavailable:'movimiento no disponible',activity:'Mayor actividad',reportedVolume:'Volumen informado US$',closing:'Cierra primero',inWord:'En',unknown:'No hay datos disponibles ahora',temporarily:'El resumen de la plataforma no está disponible temporalmente.',marketsRemain:'Los mercados siguientes siguen accesibles.',closed:'cerrado',deadlineUnknown:'plazo desconocido'}
 };
 const t=catalogs[locale]||catalogs.en;
 const panel=document.createElement('section');panel.className='venue-context';panel.id='venue-context';panel.dataset.visible='false';panel.setAttribute('aria-live','polite');panel.innerHTML=`<div class="venue-context-head"><div><h2 class="venue-context-title">${t.platformView}</h2><p class="venue-context-sub">${t.loading}</p></div></div><div class="venue-context-grid"></div>`;
 const quick=document.querySelector('.quick-filters');(quick||markets.firstElementChild)?.insertAdjacentElement('beforebegin',panel);
 const title=panel.querySelector('.venue-context-title'),sub=panel.querySelector('.venue-context-sub'),grid=panel.querySelector('.venue-context-grid');
 const pct=v=>v==null?'—':Math.round(v*100)+'%';
 const move=m=>m?.probability_change==null?t.moveUnavailable:`${m.probability_change>=0?'↑':'↓'} ${Math.abs(m.probability_change*100).toFixed(1)} pts`;
 const close=m=>{if(!m?.closes_at)return t.deadlineUnknown;const ms=new Date(m.closes_at)-Date.now();if(ms<=0)return t.closed;const h=Math.floor(ms/36e5);return h<24?`${h}h`:`${Math.floor(h/24)}d`};
 async function loadVenue(which){
   if(which==='all'){panel.dataset.visible='false';return}
   panel.dataset.visible='true';title.textContent=`${t.platformView}: ${which==='kalshi'?'Kalshi':'Polymarket'}`;sub.textContent=t.summary;grid.innerHTML=`<div class="venue-context-stat"><span>${t.status}</span><strong>${t.loadingShort}</strong></div>`;
   const venue=encodeURIComponent(which);
   try{
     const [relevant,movers,volume,closing]=await Promise.all([
       fetch(`/api/v1/markets?venue=${venue}&sort=trending&limit=1`).then(r=>{if(!r.ok)throw 0;return r.json()}),
       fetch(`/api/v1/markets?venue=${venue}&sort=movers&limit=1`).then(r=>{if(!r.ok)throw 0;return r.json()}),
       fetch(`/api/v1/markets?venue=${venue}&sort=volume&limit=1`).then(r=>{if(!r.ok)throw 0;return r.json()}),
       fetch(`/api/v1/markets/closing-soon?venue=${venue}&limit=1`).then(r=>r.ok?r.json():[])
     ]);
     const a=relevant[0],b=movers[0],c=volume[0],d=closing[0];
     const stat=(label,primary,secondary='')=>`<div class="venue-context-stat"><span>${label}</span><strong>${primary||t.unknown}</strong>${secondary?`<em>${secondary}</em>`:''}</div>`;
     const nfLocale=locale==='pt-br'?'pt-BR':locale==='es'?'es':'en-US';
     grid.innerHTML=stat(t.relevant,a?.title,a?`${t.probability} ${pct(a.probability)}`:'')+stat(t.mover,b?.title,b?move(b):'')+stat(t.activity,c?.title,c?.volume_usd!=null?`${t.reportedVolume} ${new Intl.NumberFormat(nfLocale,{notation:'compact',maximumFractionDigits:1}).format(c.volume_usd)}`:'')+stat(t.closing,d?.title,d?`${t.inWord} ${close(d)}`:'');
   }catch{grid.innerHTML=`<div class="venue-context-stat"><span>${t.status}</span><strong>${t.temporarily}</strong><em>${t.marketsRemain}</em></div>`}
 }
 document.querySelectorAll('[data-venue-link]').forEach(el=>el.addEventListener('click',()=>loadVenue(el.dataset.venueLink)));
 const initial=new URLSearchParams(location.search).get('venue');
 if(initial==='kalshi'||initial==='polymarket')loadVenue(initial);
})();
</script>'''


def enhance_home_venue_context(html: str) -> str:
    if 'id="predibeacon-venue-context-script"' in html:
        return html
    out = html.replace('</head>', STYLE + '</head>', 1) if '</head>' in html else html
    return out.replace('</body>', SCRIPT + '</body>', 1) if '</body>' in out else out
