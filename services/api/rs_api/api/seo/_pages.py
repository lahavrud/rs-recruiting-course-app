"""Prerender routes for static public pages (/about, /contact).

Split out of _routes.py — the dynamic job routes hit the DB while these are
pure content. Keeping them separate also keeps each module under the
src/api/ 200-line cap (see scripts/check_file_sizes.py).
"""

import html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from rs_shared.core.infrastructure.config import settings

from . import _jsonld as jsonld
from ._articles import get_article, list_articles
from ._content import (
    ABOUT_DESCRIPTION,
    ABOUT_HEADLINE,
    ABOUT_PROCESS_STEPS,
    ABOUT_STORY_PARAGRAPHS,
    ABOUT_TITLE,
    ABOUT_VALUES,
    ARTICLES_DESCRIPTION,
    ARTICLES_HEADLINE,
    ARTICLES_TITLE,
    CONTACT_DESCRIPTION,
    CONTACT_EMAIL,
    CONTACT_HEADLINE,
    CONTACT_SUBTITLE,
    CONTACT_TITLE,
    SITE_NAME,
)
from ._render import render_page, site_nav_html

router = APIRouter()


@router.api_route(
    "/api/og/about",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def og_about() -> HTMLResponse:
    """Server-rendered /about for crawlers.

    Static — no DB access. Mirrors the SPA's AboutPage content surface so
    Google's dynamic-rendering parity rule holds: same title, headline, story,
    values, and process that JS-rendered users see.
    """
    site_url = settings.frontend_base_url
    e = html.escape

    values_html = "".join(
        f"  <li>\n    <h3>{e(title)}</h3>\n    <p>{e(body)}</p>\n  </li>\n"
        for title, body in ABOUT_VALUES
    )
    steps_html = "".join(
        f"  <li>\n    <h3>{e(title)}</h3>\n    <p>{e(body)}</p>\n  </li>\n"
        for title, body in ABOUT_PROCESS_STEPS
    )
    story_html = "".join(f"  <p>{e(p)}</p>\n" for p in ABOUT_STORY_PARAGRAPHS)

    body_html = (
        f"<header>\n  <h1>{e(ABOUT_HEADLINE)}</h1>\n"
        f"  <p>{e(ABOUT_DESCRIPTION)}</p>\n</header>\n"
        f"{site_nav_html(site_url)}"
        f'<section aria-label="הסיפור שלנו">\n  <h2>הסיפור שלנו</h2>\n'
        f"{story_html}</section>\n"
        f'<section aria-label="הערכים שלנו">\n  <h2>הערכים שלנו</h2>\n'
        f"  <ul>\n{values_html}  </ul>\n</section>\n"
        f'<section aria-label="איך זה עובד">\n  <h2>איך זה עובד</h2>\n'
        f"  <ol>\n{steps_html}  </ol>\n</section>\n"
        f'<p><a href="{e(site_url)}/contact">צרו קשר</a></p>\n'
    )

    graph: list[dict] = [
        *jsonld.site(site_url),
        jsonld.breadcrumb([(SITE_NAME, site_url), ("אודות", f"{site_url}/about")]),
    ]

    return render_page(
        title=ABOUT_TITLE,
        description=ABOUT_DESCRIPTION,
        canonical=f"{site_url}/about",
        og_type="website",
        body_html=body_html,
        graph=graph,
    )


@router.api_route(
    "/api/og/contact",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def og_contact() -> HTMLResponse:
    """Server-rendered /contact for crawlers."""
    site_url = settings.frontend_base_url
    e = html.escape

    body_html = (
        f"<header>\n  <h1>{e(CONTACT_HEADLINE)}</h1>\n"
        f"  <p>{e(CONTACT_SUBTITLE)}</p>\n</header>\n"
        f"{site_nav_html(site_url)}"
        f'<section aria-label="פרטי קשר">\n'
        f'  <p><strong>דוא"ל:</strong> '
        f'<a href="mailto:{e(CONTACT_EMAIL)}">{e(CONTACT_EMAIL)}</a></p>\n'
        f"</section>\n"
    )

    graph: list[dict] = [
        *jsonld.site(site_url),
        jsonld.breadcrumb([(SITE_NAME, site_url), ("צרו קשר", f"{site_url}/contact")]),
    ]

    return render_page(
        title=CONTACT_TITLE,
        description=CONTACT_DESCRIPTION,
        canonical=f"{site_url}/contact",
        og_type="website",
        body_html=body_html,
        graph=graph,
    )


@router.api_route(
    "/api/og/articles",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def og_articles_index() -> HTMLResponse:
    """Server-rendered /articles index for crawlers."""
    site_url = settings.frontend_base_url
    e = html.escape
    items_html = "".join(
        f'  <li><a href="{e(site_url)}/articles/{e(a.slug)}">'
        f"<strong>{e(a.title)}</strong><br>{e(a.description)}</a></li>\n"
        for a in list_articles()
    )
    body_html = (
        f"<header>\n  <h1>{e(ARTICLES_HEADLINE)}</h1>\n"
        f"  <p>{e(ARTICLES_DESCRIPTION)}</p>\n</header>\n"
        f"{site_nav_html(site_url)}"
        '<section aria-label="רשימת מאמרים">\n  <ul>\n'
        f"{items_html}"
        "  </ul>\n</section>\n"
    )
    articles_url = f"{site_url}/articles"
    return render_page(
        title=ARTICLES_TITLE,
        description=ARTICLES_DESCRIPTION,
        canonical=articles_url,
        og_type="website",
        body_html=body_html,
        graph=[
            jsonld.breadcrumb(
                [
                    (SITE_NAME, site_url),
                    (ARTICLES_HEADLINE, articles_url),
                ]
            )
        ],
    )


@router.api_route(
    "/api/og/articles/{slug}",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def og_article(slug: str) -> HTMLResponse:
    """Server-rendered article for crawlers.

    Article markdown lives in frontend/src/content/articles/ and is copied
    into the backend image at build time (Dockerfile). Loaded once at
    import; see _articles.py.
    """
    item = get_article(slug)
    if item is None:
        raise HTTPException(status_code=404, detail="article_not_found")

    site_url = settings.frontend_base_url
    canonical = f"{site_url}/articles/{item.slug}"
    title = f"{item.title} — {SITE_NAME}"
    e = html.escape

    body_html = (
        "<header>\n"
        f'  <p><time datetime="{e(item.date)}">{e(item.date)}</time></p>\n'
        f"  <h1>{e(item.title)}</h1>\n"
        f"  <p>{e(item.description)}</p>\n"
        "</header>\n"
        f"{site_nav_html(site_url)}"
        # body_html is rendered from in-repo markdown (not user input), so
        # injecting it verbatim is safe — same trust boundary as ArticlePage.tsx.
        f"<article>\n{item.body_html}\n</article>\n"
        f'<p><a href="{e(site_url)}/articles">← כל המאמרים</a></p>\n'
    )

    graph: list[dict] = [
        jsonld.article(item, site_url),
        jsonld.breadcrumb(
            [
                (SITE_NAME, site_url),
                ("מאמרים", f"{site_url}/articles"),
                (item.title, canonical),
            ]
        ),
    ]

    return render_page(
        title=title,
        description=item.description,
        canonical=canonical,
        og_type="article",
        body_html=body_html,
        graph=graph,
    )
