from __future__ import annotations


def enhance_relevance_pages(body: str, *, path: str) -> str:
    if path == "/":
        fetch_anchor = "const r=await fetch('/api/v1/markets?'+q);"
        if fetch_anchor not in body:
            return body
        body = body.replace(
            fetch_anchor,
            "const endpoint=sort.value==='trending'?'/api/v1/markets/relevant':'/api/v1/markets';const r=await fetch(endpoint+'?'+q);",
            1,
        )
        body = body.replace("${esc(why(m))}", "${esc(m.relevance_reasons?.[0]||why(m))}", 1)
        return body

    if path == "/top":
        fetch_anchor = "fetch('/api/v1/markets?'+new URLSearchParams({sort:'trending',limit:'100'}))"
        if fetch_anchor not in body:
            return body
        return body.replace(
            fetch_anchor,
            "fetch('/api/v1/markets/relevant?'+new URLSearchParams({limit:'100'}))",
            1,
        )

    return body
