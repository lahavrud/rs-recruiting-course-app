"""HTML rendering for the SEO prerender endpoints.

``render_page`` builds the full <!doctype>/<head>/<body> document used by all
three prerender endpoints (home, jobs index, job detail). Body-specific HTML
helpers live alongside so the endpoints stay thin.
"""

import html
import json

from fastapi.responses import HTMLResponse

from src.core.infrastructure.config import settings

from ._content import (
    JOBS_HEADLINE,
    OG_DESCRIPTION_LIMIT,
    SITE_NAME,
)


def encode_jsonld_graph(graph: list[dict]) -> str:
    """JSON-encode a @graph payload for embedding inside <script>.

    html.escape covers attribute values. For the JSON-LD payload inside a
    <script> block we must also escape `<`, `>`, and `&` to unicode escapes —
    otherwise a job title containing "</script>" would break out of the
    script element (HTML parsing rules differ inside <script>; json.dumps
    alone is not enough).
    """
    payload = {"@context": "https://schema.org", "@graph": graph}
    return (
        json.dumps(payload, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render_page(
    *,
    title: str,
    description: str,
    canonical: str,
    og_type: str,
    body_html: str,
    graph: list[dict],
) -> HTMLResponse:
    e = html.escape
    site_url = settings.frontend_base_url
    og_image = f"{site_url}/hero-city.jpg"
    jsonld = encode_jsonld_graph(graph)

    truncated = description
    if len(truncated) > OG_DESCRIPTION_LIMIT:
        truncated = truncated[: OG_DESCRIPTION_LIMIT - 1].rstrip() + "…"

    body = (
        "<!doctype html>\n"
        '<html lang="he" dir="rtl">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{e(title)}</title>\n"
        f'<meta name="description" content="{e(truncated)}">\n'
        f'<link rel="canonical" href="{e(canonical)}">\n'
        f'<meta property="og:title" content="{e(title)}">\n'
        f'<meta property="og:description" content="{e(truncated)}">\n'
        f'<meta property="og:type" content="{e(og_type)}">\n'
        f'<meta property="og:site_name" content="{e(SITE_NAME)}">\n'
        f'<meta property="og:url" content="{e(canonical)}">\n'
        f'<meta property="og:image" content="{e(og_image)}">\n'
        '<meta property="og:locale" content="he_IL">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{e(title)}">\n'
        f'<meta name="twitter:description" content="{e(truncated)}">\n'
        f'<meta name="twitter:image" content="{e(og_image)}">\n'
        f'<script type="application/ld+json">{jsonld}</script>\n'
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        "</body>\n"
        "</html>\n"
    )
    # Scrapers and crawlers re-fetch periodically; an hour of cache keeps
    # content fresh for indexers without hammering the API.
    return HTMLResponse(content=body, headers={"Cache-Control": "public, max-age=3600"})


def site_nav_html(site_url: str) -> str:
    e = html.escape
    return (
        '<nav aria-label="ניווט ראשי">\n'
        "  <ul>\n"
        f'    <li><a href="{e(site_url)}/">{e(SITE_NAME)}</a></li>\n'
        f'    <li><a href="{e(site_url)}/jobs">{e(JOBS_HEADLINE)}</a></li>\n'
        "  </ul>\n"
        "</nav>\n"
    )


def format_salary(min_v: int | None, max_v: int | None) -> str | None:
    if not min_v and not max_v:
        return None
    if min_v and max_v:
        return f"{min_v:,} – {max_v:,} ₪ לחודש"
    if min_v:
        return f"החל מ-{min_v:,} ₪ לחודש"
    return f"עד {max_v:,} ₪ לחודש"
