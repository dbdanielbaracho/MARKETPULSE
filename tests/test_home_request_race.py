from __future__ import annotations

from app.services.home_page_enhancements import _serialize_discovery_loads


def _base_html() -> str:
    return """<html><body><script>
const grid=document.querySelector('#grid'),state=document.querySelector('#state'),count=document.querySelector('#count'),sort=document.querySelector('#sort'),venue=document.querySelector('#venue'),chips=[];let category='';
async function load(){state.hidden=false;grid.innerHTML='';const q=new URLSearchParams({sort:sort.value,limit:'100'});if(category)q.set('category',category);if(venue.value)q.set('venue',venue.value);try{const r=await fetch('/api/v1/markets?'+q);if(!r.ok)throw new Error();const data=await r.json();grid.innerHTML=data.map(card).join('');count.textContent=data.length+' markets';state.textContent=data.length?'':'No markets match these filters.';state.hidden=!!data.length}catch{count.textContent='Unavailable';state.className='error';state.textContent='Market discovery is temporarily unavailable. PrediBeacon will not invent replacement data.'}}
</script></body></html>"""


def test_latest_homepage_request_is_the_only_one_allowed_to_render() -> None:
    transformed = _serialize_discovery_loads(_base_html())

    assert "discoveryLoadSeq=0" in transformed
    assert "discoveryController=null" in transformed
    assert "if(discoveryController)discoveryController.abort()" in transformed
    assert "discoveryController=new AbortController()" in transformed
    assert "fetch('/api/v1/markets?'+q,{signal})" in transformed
    assert transformed.count("if(seq!==discoveryLoadSeq)return;") >= 2
    assert "error?.name==='AbortError'" in transformed


def test_new_load_resets_visible_loading_and_error_state() -> None:
    transformed = _serialize_discovery_loads(_base_html())

    assert "state.className='state'" in transformed
    assert "state.textContent='Loading market data…'" in transformed
    assert "count.textContent='Loading…'" in transformed
    assert "grid.innerHTML=''" in transformed


def test_request_race_rewrite_is_idempotent() -> None:
    once = _serialize_discovery_loads(_base_html())
    twice = _serialize_discovery_loads(once)

    assert twice == once
    assert twice.count("discoveryLoadSeq=0") == 1


def test_unrecognized_homepage_shape_fails_closed_without_partial_rewrite() -> None:
    html = "<html><script>async function load(){/* changed upstream */}</script></html>"
    assert _serialize_discovery_loads(html) == html
