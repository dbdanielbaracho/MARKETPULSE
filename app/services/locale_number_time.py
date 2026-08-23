from __future__ import annotations


_MONEY_OLD = "function money(v){return v==null?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact'}).format(v)}"
_MONEY_NEW = "function money(v){return v==null?'Unavailable':new Intl.NumberFormat(document.documentElement.lang||'en',{style:'currency',currency:'USD',notation:'compact'}).format(v)}"

_REMAINING_OLD = "function remaining(v){if(!v)return'Not published';const ms=new Date(v).getTime()-Date.now();if(ms<=0)return'Closed';const h=Math.floor(ms/3600000);if(h<24)return h+'h';return Math.floor(h/24)+'d '+h%24+'h'}"
_REMAINING_NEW = "function remaining(v){if(!v)return'Not published';const ms=new Date(v).getTime()-Date.now();if(ms<=0)return'Closed';const locale=document.documentElement.lang||'en',rtf=new Intl.RelativeTimeFormat(locale,{numeric:'always'}),h=Math.floor(ms/3600000);if(h<24)return rtf.format(h,'hour');const d=Math.floor(h/24);return rtf.format(d,'day')}"

_AGO_OLD = "function ago(v){const ms=Date.now()-new Date(v).getTime();if(!Number.isFinite(ms)||ms<0)return'Unknown';const m=Math.floor(ms/60000);return m<1?'Just now':m<60?m+'m ago':Math.floor(m/60)+'h ago'}"
_AGO_NEW = "function ago(v){const ms=Date.now()-new Date(v).getTime();if(!Number.isFinite(ms)||ms<0)return'Unknown';const locale=document.documentElement.lang||'en',rtf=new Intl.RelativeTimeFormat(locale,{numeric:'auto'}),m=Math.floor(ms/60000);if(m<1)return rtf.format(0,'minute');if(m<60)return rtf.format(-m,'minute');return rtf.format(-Math.floor(m/60),'hour')}"


def localize_market_formatting(path: str, html: str) -> str:
    """Use browser-standard Intl formatting for user-visible market numbers/time.

    Venue contract titles remain canonical and untranslated. Only presentation of
    currency and relative time is localized, using the final document language
    chosen by PrediBeacon's existing language negotiation/override layer.
    """
    if not (path == "/market" or path.startswith("/markets/")):
        return html
    return (
        html.replace(_MONEY_OLD, _MONEY_NEW)
        .replace(_REMAINING_OLD, _REMAINING_NEW)
        .replace(_AGO_OLD, _AGO_NEW)
    )
