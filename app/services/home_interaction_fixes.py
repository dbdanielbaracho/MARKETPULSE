from __future__ import annotations

STYLE = r'''<style id="predibeacon-home-interaction-fixes-style">
.hero-v2{grid-template-columns:minmax(0,.9fr) minmax(0,1.3fr);gap:clamp(1.35rem,3vw,2.6rem)}
.hero-v2>div{min-width:0}.hero-v2>div:first-child{max-width:680px}.hero-v2>div:last-child{width:100%}
.venue-hub{width:100%;grid-template-columns:minmax(0,1fr) minmax(0,.95fr) minmax(0,1fr)}
.venue-card,.beacon-core{width:100%;box-sizing:border-box}.venue-chart{pointer-events:none}
@media(max-width:1180px){.hero-v2{grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:1.5rem}.hero-v2 h1{font-size:clamp(2.45rem,4.8vw,4rem)}}
@media(max-width:980px){.hero-v2{grid-template-columns:1fr}.hero-v2>div:first-child{max-width:760px}.hero-v2>div:last-child{max-width:760px}.hero-v2{margin-inline:auto}}
@media(max-width:720px){.venue-hub{grid-template-columns:1fr 1fr}.beacon-core{grid-column:1/-1;grid-row:1}}
@media(max-width:520px){.venue-hub{grid-template-columns:1fr}.beacon-core{grid-column:auto}}
</style>'''

SCRIPT = r'''<script id="predibeacon-home-interaction-fixes-script">
(()=>{
 const hub=document.querySelector('.venue-hub');
 const venue=document.querySelector('#venue');
 const markets=document.querySelector('#markets');
 if(!hub||!venue||!markets)return;
 const normalized=v=>v==='kalshi'||v==='polymarket'?v:'all';
 const hrefFor=v=>v==='all'?'/?venue=all#markets':`/?venue=${encodeURIComponent(v)}#markets`;
 const syncSelected=v=>{
   const value=v==='all'?'':v;
   venue.value=value;
   document.querySelectorAll('[data-venue-link]').forEach(x=>x.dataset.active=String(x.dataset.venueLink===v));
   venue.dispatchEvent(new Event('change',{bubbles:true}));
 };
 const navigate=v=>{
   const target=hrefFor(v);
   const current=location.pathname+location.search+location.hash;
   if(current===target){
     syncSelected(v);
     markets.scrollIntoView({behavior:'smooth',block:'start'});
     return;
   }
   location.assign(target);
 };
 hub.querySelectorAll('[data-venue-link]').forEach(el=>{
   const v=normalized(el.dataset.venueLink);
   if(el.tagName==='A')el.setAttribute('href',hrefFor(v));
   el.setAttribute('title',v==='kalshi'?'Ver todos os mercados Kalshi':v==='polymarket'?'Ver todos os mercados Polymarket':'Ver Kalshi e Polymarket juntos');
   el.addEventListener('click',e=>{
     e.preventDefault();
     e.stopImmediatePropagation();
     navigate(v);
   },true);
 });
 const params=new URLSearchParams(location.search);
 const initial=normalized(params.get('venue'));
 if(params.has('venue')){
   setTimeout(()=>{
     syncSelected(initial);
     if(location.hash==='#markets')markets.scrollIntoView({block:'start'});
   },0);
 }
})();
</script>'''


def enhance_home_interactions(html: str) -> str:
    if 'id="predibeacon-home-interaction-fixes-script"' in html:
        return html
    out = html.replace('</head>', STYLE + '</head>', 1) if '</head>' in html else html
    return out.replace('</body>', SCRIPT + '</body>', 1) if '</body>' in out else out
