from __future__ import annotations

SCRIPT = r'''<script id="predibeacon-home-card-localization-script">
(()=>{
 const grid=document.querySelector('#grid');if(!grid)return;
 function text(el,from,to){if(el&&el.textContent.trim()===from)el.textContent=to}
 function localize(card){
   const status=card.querySelector('.status');text(status,'Open','Aberto');text(status,'Closed','Encerrado');
   const insight=card.querySelector('.insight');if(insight&&insight.innerHTML.includes('<strong>Why it matters:</strong>'))insight.innerHTML=insight.innerHTML.replace('<strong>Why it matters:</strong>','<strong>Por que importa:</strong>');
   const facts=[...card.querySelectorAll('.fact')];
   for(const fact of facts){const first=[...fact.childNodes].find(n=>n.nodeType===Node.TEXT_NODE);if(!first)continue;const label=first.textContent.trim();if(label==='Volume')first.textContent='Volume ';else if(label==='Closes in')first.textContent='Fecha em ';else if(label==='Trend')first.textContent='Relevância '}
   const primary=card.querySelector('.actions .primary');text(primary,'View PrediBeacon analysis','Ver análise PrediBeacon');
   const watch=card.querySelector('.watch');if(watch){text(watch,'Watch','Acompanhar');text(watch,'Watching','Acompanhando')}
   card.dataset.locale='pt-BR';
 }
 function scan(){for(const card of grid.querySelectorAll('.card'))localize(card)}
 new MutationObserver(scan).observe(grid,{childList:true,subtree:true});scan();
 const count=document.querySelector('#count');if(count){new MutationObserver(()=>{count.textContent=count.textContent.replace(/\bmarkets\b/g,'mercados').replace(/\bmarket\b/g,'mercado').replace('Unavailable','Indisponível')}).observe(count,{childList:true,characterData:true,subtree:true})}
})();
</script>'''


def enhance_home_card_localization(html: str) -> str:
    if 'id="predibeacon-home-card-localization-script"' in html:
        return html
    return html.replace('</body>', SCRIPT + '</body>', 1) if '</body>' in html else html
