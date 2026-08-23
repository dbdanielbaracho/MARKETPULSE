from __future__ import annotations

STYLE = r'''<style id="predibeacon-mobile-funnel-style">
@media(max-width:720px){
 body{padding-bottom:76px}.wrap{width:min(100% - 24px,var(--max))}.hero-v2{padding:1.15rem 0 .8rem;gap:1rem}.hero-v2 h1{font-size:clamp(2rem,10vw,2.8rem);line-height:1.04}.hero-copy{font-size:.96rem}
 .trust-row{display:grid;grid-template-columns:1fr 1fr;gap:.45rem}.trust-pill:last-child{grid-column:1/-1}.vision-label{text-align:left;margin-top:.35rem}.venue-hub{display:grid;grid-template-columns:1fr;gap:.55rem}
 .beacon-core{grid-column:auto;grid-row:auto;order:-1;min-height:72px}.beacon-graphic{display:none}.venue-card{min-height:92px;padding:.85rem}.venue-chart{display:none}.venue-count{font-size:1.35rem;margin:.25rem 0}.venue-cta{padding-top:.25rem}
 .change-strip{width:min(100% - 24px,var(--max));margin:0 auto 1rem;padding:.55rem;gap:.35rem;scroll-snap-type:x mandatory}.change-title{min-width:128px}.change-item{min-width:78vw;scroll-snap-align:start}
 .quick-filters{display:grid;grid-template-columns:1fr 1fr;gap:.45rem;margin:.7rem 0}.quick-filter{min-height:48px;padding:.55rem}.controls{gap:.55rem}.controls label{width:100%}.controls select{width:100%;min-height:48px}
 .chips{display:flex;overflow-x:auto;flex-wrap:nowrap;padding-bottom:.35rem;scroll-snap-type:x proximity}.chip{min-height:44px;white-space:nowrap;scroll-snap-align:start}.grid{padding-bottom:1rem}
 .card[data-home-row="ready"]{display:block;padding:.9rem;margin-bottom:.65rem;border-radius:14px}.market-summary h3{font-size:1rem}.prediction-summary{display:flex;align-items:baseline;gap:.55rem}.prediction-summary .prob{font-size:2rem;margin-top:.7rem}
 .card[data-home-row="ready"] .facts{display:grid;grid-template-columns:1fr 1fr;gap:.4rem}.card[data-home-row="ready"] .fact{font-size:.78rem}.card[data-home-row="ready"] .platform-availability{min-height:0;margin-top:.65rem}
 .card[data-home-row="ready"] .actions{display:grid;grid-template-columns:1fr;gap:.45rem;margin-top:.7rem}.card[data-home-row="ready"] .actions a,.card[data-home-row="ready"] .actions button{min-height:50px;width:100%;justify-content:center}
 .pb-mobile-nav{position:fixed;left:0;right:0;bottom:0;z-index:60;display:grid;grid-template-columns:repeat(4,1fr);background:#090d14f2;border-top:1px solid #273244;padding:.4rem .35rem max(.4rem,env(safe-area-inset-bottom));backdrop-filter:blur(14px)}
 .pb-mobile-nav a{display:flex;min-height:48px;align-items:center;justify-content:center;text-align:center;text-decoration:none;font-size:.75rem;font-weight:800;color:#d6deea;border-radius:10px}.pb-mobile-nav a:focus-visible{outline:3px solid #8be9c7;outline-offset:2px}
}@media(max-width:420px){.card[data-home-row="ready"] .facts{grid-template-columns:1fr}}@media(min-width:721px){.pb-mobile-nav{display:none}}
</style>'''
NAV = '''<nav class="pb-mobile-nav" aria-label="Mobile navigation"><a href="/">Home</a><a href="/#markets">Explore</a><a href="/watchlist">Watchlist</a><a href="/alerts">Alerts</a></nav>'''

def enhance_mobile_funnel(html: str) -> str:
    if 'id="predibeacon-mobile-funnel-style"' in html:
        return html
    out = html.replace('</head>', STYLE + '</head>', 1) if '</head>' in html else html
    return out.replace('</body>', NAV + '</body>', 1) if '</body>' in out else out
