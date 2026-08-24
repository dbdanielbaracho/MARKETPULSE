from app.services.locale_number_time import localize_market_formatting


def test_market_formatting_replaces_hardcoded_us_locale():
    source = "function money(v){return v==null?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact'}).format(v)}"
    result = localize_market_formatting('/markets/example-market-abcdef12', source)
    assert "Intl.NumberFormat(document.documentElement.lang||'en'" in result
    assert "Intl.NumberFormat('en-US'" not in result


def test_market_formatting_uses_standard_relative_time_api():
    source = "function remaining(v){if(!v)return'Not published';const ms=new Date(v).getTime()-Date.now();if(ms<=0)return'Closed';const h=Math.floor(ms/3600000);if(h<24)return h+'h';return Math.floor(h/24)+'d '+h%24+'h'}function ago(v){const ms=Date.now()-new Date(v).getTime();if(!Number.isFinite(ms)||ms<0)return'Unknown';const m=Math.floor(ms/60000);return m<1?'Just now':m<60?m+'m ago':Math.floor(m/60)+'h ago'}"
    result = localize_market_formatting('/market', source)
    assert result.count('Intl.RelativeTimeFormat') == 2
    assert "m+'m ago'" not in result
    assert "h+'h'" not in result


def test_non_market_pages_are_not_rewritten():
    source = "new Intl.NumberFormat('en-US')"
    assert localize_market_formatting('/privacy', source) == source


def test_full_market_script_snippets_are_rewritten_together():
    source = (
        "function money(v){return v==null?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact'}).format(v)}"
        "function remaining(v){if(!v)return'Not published';const ms=new Date(v).getTime()-Date.now();if(ms<=0)return'Closed';const h=Math.floor(ms/3600000);if(h<24)return h+'h';return Math.floor(h/24)+'d '+h%24+'h'}"
        "function ago(v){const ms=Date.now()-new Date(v).getTime();if(!Number.isFinite(ms)||ms<0)return'Unknown';const m=Math.floor(ms/60000);return m<1?'Just now':m<60?m+'m ago':Math.floor(m/60)+'h ago'}"
        "document.querySelector('#remaining').textContent=remaining(m.closes_at);"
        "document.querySelector('#observed').textContent=ago(m.observed_at);"
    )
    result = localize_market_formatting('/markets/example-market-abcdef12', source)
    assert "Intl.NumberFormat(document.documentElement.lang||'en'" in result
    assert result.count('Intl.RelativeTimeFormat') == 2
    assert "Intl.NumberFormat('en-US'" not in result
    assert "Intl.DateTimeFormat" in result
    assert "timeZoneName:'short'" in result
    assert "remainingEl.title=absoluteTime(m.closes_at)" in result
    assert "observedEl.title=absoluteTime(m.observed_at)" in result


def test_absolute_timestamp_formatter_is_not_injected_without_timestamp_targets():
    source = "function ago(v){const ms=Date.now()-new Date(v).getTime();if(!Number.isFinite(ms)||ms<0)return'Unknown';const m=Math.floor(ms/60000);return m<1?'Just now':m<60?m+'m ago':Math.floor(m/60)+'h ago'}"
    result = localize_market_formatting('/market', source)
    assert "Intl.DateTimeFormat" not in result
