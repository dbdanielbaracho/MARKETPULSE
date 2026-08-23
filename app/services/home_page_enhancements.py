from __future__ import annotations


_HOME_STYLE = r'''<style id="predibeacon-home-platform-visibility-style">
.platform-availability{margin-top:.8rem;border:1px solid var(--line);border-radius:12px;padding:.75rem .85rem;background:rgba(0,0,0,.12);font-size:.84rem;line-height:1.45}.platform-availability strong{display:block;color:var(--text);margin-bottom:.2rem}.platform-availability .muted{color:var(--muted)}.platform-availability .verified-other{color:var(--accent);font-weight:850}.platform-availability .candidate-other{color:#fbbf24;font-weight:800}.platform-availability .single-venue{color:var(--muted);font-weight:750}
</style>'''


_HOME_SCRIPT = r'''<script id="predibeacon-home-platform-visibility-script">
(()=>{
  const checked=new Map();
  const inFlight=new Map();
  const otherVenue=venue=>venue==='kalshi'?'Polymarket':'Kalshi';
  const venueLabel=venue=>venue==='kalshi'?'Kalshi':'Polymarket';
  const probability=v=>v==null?'':` · ${Math.round(Number(v)*100)}% there`;

  function ensurePanel(card,id,venue){
    let panel=card.querySelector('.platform-availability');
    if(panel)return panel;
    panel=document.createElement('div');
    panel.className='platform-availability';
    panel.dataset.marketId=id;
    panel.dataset.venue=venue;
    panel.setAttribute('role','status');
    panel.setAttribute('aria-live','polite');
    panel.innerHTML=`<strong>Available on ${venueLabel(venue)}</strong><span class="muted">Checking ${otherVenue(venue)} for the same contract…</span>`;
    const actions=card.querySelector('.actions');
    if(actions)card.insertBefore(panel,actions);else card.append(panel);
    return panel;
  }

  function render(panel,result,venue){
    const current=venueLabel(venue),other=otherVenue(venue);
    if(!result){
      panel.innerHTML=`<strong>Available on ${current}</strong><span class="muted">Cross-platform check temporarily unavailable.</span>`;
      return;
    }
    const counterpart=result.counterpart;
    const verification=result.verification;
    if(counterpart&&verification?.equivalent_contracts){
      panel.innerHTML=`<strong>Available on ${current}</strong><span class="verified-other">Also on ${venueLabel(counterpart.venue)} · verified equivalent${probability(counterpart.probability)}</span><br><span class="muted">Verification confidence ${verification.confidence}/100.</span>`;
      return;
    }
    if(counterpart){
      panel.innerHTML=`<strong>Available on ${current}</strong><span class="candidate-other">Similar market found on ${venueLabel(counterpart.venue)}, but it is not verified as the same contract.</span>`;
      return;
    }
    panel.innerHTML=`<strong>Available on ${current}</strong><span class="single-venue">No verified equivalent found on ${other}.</span>`;
  }

  async function lookup(id,venue,panel){
    if(checked.has(id)){render(panel,checked.get(id),venue);return}
    if(inFlight.has(id)){render(panel,await inFlight.get(id),venue);return}
    const promise=(async()=>{
      try{
        const r=await fetch('/api/v1/market/cross-platform?'+new URLSearchParams({market_id:id,candidate_limit:'3'}));
        if(!r.ok)throw new Error('unavailable');
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


def enhance_home_template(html: str) -> str:
    """Add per-card cross-platform availability without changing the base template."""
    if 'id="predibeacon-home-platform-visibility-script"' in html:
        return html
    enhanced = html
    if "</head>" in enhanced:
        enhanced = enhanced.replace("</head>", _HOME_STYLE + "</head>", 1)
    if "</body>" in enhanced:
        enhanced = enhanced.replace("</body>", _HOME_SCRIPT + "</body>", 1)
    return enhanced
