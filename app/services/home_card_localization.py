from __future__ import annotations

SCRIPT = r'''<script id="predibeacon-home-card-localization-script">
(()=>{
 const grid=document.querySelector('#grid');if(!grid)return;
 const locale=(document.documentElement.lang||'en').toLowerCase();
 const catalog={
   en:{open:'Open',closed:'Closed',why:'Why it matters:',volume:'Volume',closes:'Closes in',trend:'Trend',analysis:'View PrediBeacon analysis',watch:'Watch',watching:'Watching',market:'market',markets:'markets',unavailable:'Unavailable'},
   'pt-br':{open:'Aberto',closed:'Encerrado',why:'Por que importa:',volume:'Volume',closes:'Fecha em',trend:'Relevância',analysis:'Ver análise PrediBeacon',watch:'Acompanhar',watching:'Acompanhando',market:'mercado',markets:'mercados',unavailable:'Indisponível'},
   es:{open:'Abierto',closed:'Cerrado',why:'Por qué importa:',volume:'Volumen',closes:'Cierra en',trend:'Relevancia',analysis:'Ver análisis PrediBeacon',watch:'Seguir',watching:'Siguiendo',market:'mercado',markets:'mercados',unavailable:'No disponible'}
 };
 const t=catalog[locale]||catalog.en;
 function setExact(el,values,to){if(el&&values.includes(el.textContent.trim()))el.textContent=to}
 function localize(card){
   const status=card.querySelector('.status');setExact(status,['Open','Aberto','Abierto'],t.open);setExact(status,['Closed','Encerrado','Cerrado'],t.closed);
   const insight=card.querySelector('.insight');if(insight){for(const source of ['Why it matters:','Por que importa:','Por qué importa:']){if(insight.innerHTML.includes(`<strong>${source}</strong>`)){insight.innerHTML=insight.innerHTML.replace(`<strong>${source}</strong>`,`<strong>${t.why}</strong>`);break}}}
   const facts=[...card.querySelectorAll('.fact')];
   for(const fact of facts){const first=[...fact.childNodes].find(n=>n.nodeType===Node.TEXT_NODE);if(!first)continue;const label=first.textContent.trim();if(['Volume','Volumen'].includes(label))first.textContent=t.volume+' ';else if(['Closes in','Fecha em','Cierra en'].includes(label))first.textContent=t.closes+' ';else if(['Trend','Relevância','Relevancia'].includes(label))first.textContent=t.trend+' '}
   const primary=card.querySelector('.actions .primary');setExact(primary,['View PrediBeacon analysis','Ver análise PrediBeacon','Ver análisis PrediBeacon'],t.analysis);
   const watch=card.querySelector('.watch');if(watch){setExact(watch,['Watch','Acompanhar','Seguir'],t.watch);setExact(watch,['Watching','Acompanhando','Siguiendo'],t.watching)}
   card.dataset.locale=document.documentElement.lang||'en';
 }
 function scan(){for(const card of grid.querySelectorAll('.card'))localize(card)}
 new MutationObserver(scan).observe(grid,{childList:true,subtree:true});scan();
 const count=document.querySelector('#count');if(count){new MutationObserver(()=>{const value=count.textContent.trim();const m=value.match(/^(\d+)\s+(?:markets?|mercados?)$/i);if(m)count.textContent=m[1]+' '+(m[1]==='1'?t.market:t.markets);else if(['Unavailable','Indisponível','No disponible'].includes(value))count.textContent=t.unavailable}).observe(count,{childList:true,characterData:true,subtree:true})}
})();
</script>'''


def enhance_home_card_localization(html: str) -> str:
    if 'id="predibeacon-home-card-localization-script"' in html:
        return html
    return html.replace('</body>', SCRIPT + '</body>', 1) if '</body>' in html else html
