from __future__ import annotations


_EXECUTION_PANEL = '''<section class="panel"><div class="eyebrow">EXECUTION QUALITY</div><h2>What does the visible order book look like?</h2><div id="execution-quality" class="cross" role="status" aria-live="polite"><span class="muted">Checking displayed spread and depth…</span></div><p class="notice">Execution Quality describes the currently displayed order book. It does not include every fee or trading friction and is not a fill, liquidity, profitability or best-execution guarantee.</p></section>'''

_EXECUTION_SCRIPT = r'''async function loadExecutionQuality(){const target=document.querySelector('#execution-quality');if(!target||!id)return;try{const r=await fetch('/api/v1/market/execution-quality?'+new URLSearchParams({market_id:id}));if(!r.ok)throw new Error();const d=await r.json();target.replaceChildren();if(!d.available){const message=document.createElement('span');message.className='muted';message.textContent=(d.reasons||[]).join(' · ')||'A two-sided displayed order book is not available right now.';target.append(message);return}const grade=document.createElement('strong');grade.textContent='Execution Quality '+String(d.score??'—')+'/100 · '+String(d.grade||'').toUpperCase();target.append(grade);const grid=document.createElement('div');grid.className='crossgrid';const values=[['Best bid',d.best_bid==null?'—':Math.round(d.best_bid*100)+'%'],['Best ask',d.best_ask==null?'—':Math.round(d.best_ask*100)+'%'],['Spread',d.spread_points==null?'—':Number(d.spread_points).toFixed(2)+' pts'],['Bid depth',d.bid_depth_units==null?'—':Number(d.bid_depth_units).toLocaleString('en-US')+' units'],['Ask depth',d.ask_depth_units==null?'—':Number(d.ask_depth_units).toLocaleString('en-US')+' units'],['Midpoint',d.midpoint==null?'—':Math.round(d.midpoint*100)+'%']];for(const[label,value]of values){const box=document.createElement('div'),name=document.createElement('span'),number=document.createElement('div');name.className='muted';name.textContent=label;number.className='crossvalue';number.textContent=value;box.append(name,number);grid.append(box)}target.append(grid);if(d.reasons?.length){const note=document.createElement('p');note.className='muted';note.textContent=d.reasons.join(' · ');target.append(note)}}catch{target.replaceChildren();const message=document.createElement('span');message.className='muted';message.textContent='Execution Quality is temporarily unavailable. PrediBeacon will not infer missing order-book data.';target.append(message)}}'''


def enhance_market_template(body: str) -> str:
    """Add consumer execution-quality UI without coupling venue logic to the template."""
    panel_anchor = '<section class="panel"><div class="eyebrow">CROSS-PLATFORM CHECK</div>'
    script_anchor = 'async function loadSignals()'
    startup_anchor = 'loadMarket();loadSignals();'
    if panel_anchor not in body or script_anchor not in body or startup_anchor not in body:
        return body
    body = body.replace(panel_anchor, _EXECUTION_PANEL + panel_anchor, 1)
    body = body.replace(script_anchor, _EXECUTION_SCRIPT + script_anchor, 1)
    body = body.replace(
        startup_anchor,
        'loadMarket();loadExecutionQuality();loadSignals();setInterval(loadExecutionQuality,30000);',
        1,
    )
    return body
