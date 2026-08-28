from __future__ import annotations

SCRIPT = r'''<script id="predibeacon-home-card-localization-script">
(()=>{
 const grid=document.querySelector('#grid');if(!grid)return;
 const locale=(document.documentElement.lang||'en').toLowerCase();
 const catalog={
   en:{open:'Open',closed:'Closed',why:'Why it matters:',volume:'Volume',closes:'Closes in',trend:'Trend',analysis:'View PrediBeacon analysis',watch:'Watch',watching:'Watching',market:'market',markets:'markets',unavailable:'Unavailable',changeUnavailable:'Change unavailable',stableMove:'No material move'},
   'pt-br':{open:'Aberto',closed:'Encerrado',why:'Por que importa:',volume:'Volume',closes:'Fecha em',trend:'Relevância',analysis:'Ver análise PrediBeacon',watch:'Acompanhar',watching:'Acompanhando',market:'mercado',markets:'mercados',unavailable:'Indisponível',changeUnavailable:'Variação indisponível',stableMove:'Sem movimento relevante'},
   es:{open:'Abierto',closed:'Cerrado',why:'Por qué importa:',volume:'Volumen',closes:'Cierra en',trend:'Relevancia',analysis:'Ver análisis PrediBeacon',watch:'Seguir',watching:'Siguiendo',market:'mercado',markets:'mercados',unavailable:'No disponible',changeUnavailable:'Variación no disponible',stableMove:'Sin movimiento relevante'}
 };
 const t=catalog[locale]||catalog.en;
 function setExact(el,values,to){if(!el)return;const current=el.textContent.trim();if(values.includes(current)&&current!==to)el.textContent=to}
 function setTextNode(node,to){if(!node)return;const current=node.textContent.trim();if(current!==to)node.textContent=to+' '}
 function localize(card){
   const status=card.querySelector('.status');setExact(status,['Open','Aberto','Abierto'],t.open);setExact(status,['Closed','Encerrado','Cerrado'],t.closed);
   const move=card.querySelector('.move');
   setExact(move,['Change unavailable','Variação indisponível','Variación no disponible'],t.changeUnavailable);
   if(move&&/^[▲▼]\s*0(?:[.,]0)?\s*pts$/i.test(move.textContent.trim()))move.textContent=t.stableMove;
   const insight=card.querySelector('.insight');if(insight){for(const source of ['Why it matters:','Por que importa:','Por qué importa:']){const from=`<strong>${source}</strong>`,to=`<strong>${t.why}</strong>`;if(source!==t.why&&insight.innerHTML.includes(from)){const next=insight.innerHTML.replace(from,to);if(next!==insight.innerHTML)insight.innerHTML=next;break}}}
   const facts=[...card.querySelectorAll('.fact')];
   for(const fact of facts){const first=[...fact.childNodes].find(n=>n.nodeType===Node.TEXT_NODE);if(!first)continue;const label=first.textContent.trim();if(['Volume','Volumen'].includes(label))setTextNode(first,t.volume);else if(['Closes in','Fecha em','Cierra en'].includes(label))setTextNode(first,t.closes);else if(['Trend','Relevância','Relevancia'].includes(label))setTextNode(first,t.trend)}
   const primary=card.querySelector('.actions .primary');setExact(primary,['View PrediBeacon analysis','Ver análise PrediBeacon','Ver análisis PrediBeacon'],t.analysis);
   const watch=card.querySelector('.watch');if(watch){setExact(watch,['Watch','Acompanhar','Seguir'],t.watch);setExact(watch,['Watching','Acompanhando','Siguiendo'],t.watching)}
   const lang=document.documentElement.lang||'en';if(card.dataset.locale!==lang)card.dataset.locale=lang;
 }
 let scanning=false;
 function scan(){if(scanning)return;scanning=true;try{for(const card of grid.querySelectorAll('.card'))localize(card)}finally{scanning=false}}
 new MutationObserver(scan).observe(grid,{childList:true,subtree:true});scan();
 const count=document.querySelector('#count');if(count){new MutationObserver(()=>{const value=count.textContent.trim();const m=value.match(/^(\d+)\s+(?:markets?|mercados?)$/i);let next=null;if(m)next=m[1]+' '+(m[1]==='1'?t.market:t.markets);else if(['Unavailable','Indisponível','No disponible'].includes(value))next=t.unavailable;if(next!==null&&next!==value)count.textContent=next}).observe(count,{childList:true,characterData:true,subtree:true})}
})();
</script>'''


def enhance_home_card_localization(html: str) -> str:
    if 'id="predibeacon-home-card-localization-script"' in html:
        return html
    return html.replace('</body>', SCRIPT + '</body>', 1) if '</body>' in html else html
