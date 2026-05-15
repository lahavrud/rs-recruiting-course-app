"""SEO endpoints: /robots.txt, /sitemap.xml, and /api/og/* prerender routes.

The /api/og/* routes serve a server-rendered HTML version of public pages.
nginx routes traffic here for:
  - social-preview scrapers (LinkedIn, WhatsApp, Twitter, Slack, …) — they
    don't execute JS and need a fully-meta'd <head>.
  - search engine crawlers (Googlebot, Googlebot-Mobile, Bingbot) — Google
    does render JS but the second-stage queue is slow and unreliable; serving
    a fully-rendered HTML document gets us indexed faster and more
    completely, with the same JSON-LD the SPA emits.

Real browsers still fall through to the SPA.
"""

import html
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.enums import JobStatus
from src.models import Job

router = APIRouter()

SITE_NAME = "RS Recruiting"
_OG_DESCRIPTION_LIMIT = 160
_JOBS_INDEX_LIMIT = 50

# Google drops JobPostings from rich results after 6 months without an
# explicit validThrough. 90 days matches typical Israeli recruitment cadence —
# admins can refresh by editing the job (updated_at change → sitemap lastmod).
_JOB_POSTING_VALID_DAYS = 90

# Routes that should never appear in search results: authenticated areas and
# auth flow pages. Public routes (/, /jobs, /jobs/:id) remain crawlable.
_DISALLOWED_PATHS = (
    "/admin",
    "/admin/",
    "/company",
    "/company/",
    "/dashboard",
    "/activate",
    "/login",
    "/register",
)

_SITEMAP_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
_SITEMAP_FOOTER = "</urlset>"

# Hebrew copy for prerendered pages. Mirrors the SPA's `landing.seo.*` and
# `publicJobs.board.*` i18n keys — duplicated here because the prerender
# endpoints run server-side without access to the frontend's locale bundle.
# Keep in sync with frontend/src/locales/he.json when wording changes.
_HOME_HEADLINE = "גיוס לתפקידי ניהול ותפעול מבנים ונכסים"
_HOME_DESCRIPTION = (
    "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול מבנים ונכסים. "
    "חיפוש עבודה עם ליווי אישי ושיבוץ מדויק."
)
_JOBS_HEADLINE = "משרות בתחום ניהול ותפעול מבנים"
_JOBS_DESCRIPTION = (
    "כל המשרות הפתוחות בתחום ניהול ותפעול נכסים ומבנים — "
    "תפקידי ניהול, תפעול, אחזקה, בנייה, נדל״ן ועוד."
)


# ─────────────────────────────────────────────────────────────────────────────
# robots.txt + sitemap.xml
# ─────────────────────────────────────────────────────────────────────────────


def _url_entry(loc: str, lastmod: str | None = None, changefreq: str = "weekly") -> str:
    mod = f"  <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    freq = f"  <changefreq>{changefreq}</changefreq>\n"
    return f"  <url>\n  <loc>{loc}</loc>\n{mod}{freq}  </url>\n"


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt() -> str:
    sitemap_url = f"{settings.frontend_base_url}/sitemap.xml"
    disallow = "\n".join(f"Disallow: {p}" for p in _DISALLOWED_PATHS)
    return f"User-agent: *\nAllow: /\n{disallow}\nSitemap: {sitemap_url}\n"


@router.get("/sitemap.xml", response_class=PlainTextResponse, include_in_schema=False)
async def sitemap_xml(session: AsyncSession = Depends(get_session)) -> str:
    base = settings.frontend_base_url
    today = datetime.now(UTC).date().isoformat()

    result = await session.execute(
        select(Job.id, Job.updated_at).where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
    )
    jobs = result.all()

    entries = _url_entry(f"{base}/", changefreq="monthly")
    entries += _url_entry(f"{base}/jobs", lastmod=today, changefreq="daily")
    for job_id, updated_at in jobs:
        lastmod = updated_at.date().isoformat() if updated_at else today
        entries += _url_entry(f"{base}/jobs/{job_id}", lastmod=lastmod)

    return _SITEMAP_HEADER + entries + _SITEMAP_FOOTER


# ─────────────────────────────────────────────────────────────────────────────
# JSON-LD builders
# ─────────────────────────────────────────────────────────────────────────────


def _description_html(job: Job) -> str:
    """Render description + requirements as HTML for JSON-LD.

    Google's JobPosting spec requires `description` to be HTML so paragraphs
    and bullet lists render in the rich result. Plain text with `\\n` does not.
    """
    parts: list[str] = []
    for paragraph in job.description.split("\n\n"):
        text = paragraph.strip()
        if text:
            parts.append(f"<p>{html.escape(text)}</p>")
    items = [
        f"<li>{html.escape(req['text'])}</li>"
        for req in job.requirements
        if isinstance(req, dict) and req.get("text")
    ]
    if items:
        parts.append("<ul>" + "".join(items) + "</ul>")
    return "".join(parts)


def _build_job_posting_jsonld(job: Job, site_url: str) -> dict:
    valid_through = job.created_at + timedelta(days=_JOB_POSTING_VALID_DAYS)
    posting: dict = {
        "@type": "JobPosting",
        "title": job.title,
        "description": _description_html(job),
        "datePosted": job.created_at.isoformat(),
        "validThrough": valid_through.isoformat(),
        "employmentType": "FULL_TIME",
        "directApply": True,
        "identifier": {
            "@type": "PropertyValue",
            "name": SITE_NAME,
            "value": str(job.id),
        },
        "url": f"{site_url}/jobs/{job.id}",
        "hiringOrganization": {
            "@type": "Organization",
            "name": SITE_NAME,
            "sameAs": site_url,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.location,
                "addressCountry": "IL",
            },
        },
    }
    if job.salary_min and job.salary_max:
        posting["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": "ILS",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": job.salary_min,
                "maxValue": job.salary_max,
                "unitText": "MONTH",
            },
        }
    return posting


def _site_jsonld(site_url: str) -> list[dict]:
    """Organization + EmploymentAgency + WebSite — matches LandingPage SITE_SCHEMA.

    Shared @id between Organization and WebSite gives Google a single canonical
    brand entity for the domain (helps consolidate the homepage and /jobs into
    a single SERP entry).
    """
    return [
        {
            "@type": ["Organization", "EmploymentAgency"],
            "@id": f"{site_url}/#organization",
            "name": SITE_NAME,
            "url": site_url,
            "logo": f"{site_url}/logo.svg",
            "description": (
                "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול "
                "מבנים ונכסים בישראל"
            ),
            "areaServed": "IL",
            "knowsAbout": [
                "ניהול מבנים",
                "תפעול מבנים",
                "ניהול נכסים",
                "גיוס עובדים",
                "השמה",
            ],
            "contactPoint": {
                "@type": "ContactPoint",
                "email": "support@rs-recruiting.com",
                "contactType": "כוח אדם וגיוס",
                "areaServed": "IL",
                "availableLanguage": "Hebrew",
            },
        },
        {
            "@type": "WebSite",
            "@id": f"{site_url}/#website",
            "url": site_url,
            "name": SITE_NAME,
            "inLanguage": "he-IL",
            "publisher": {"@id": f"{site_url}/#organization"},
        },
    ]


def _breadcrumb_jsonld(items: Sequence[tuple[str, str]]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }


def _itemlist_jsonld(jobs: list[Job], site_url: str) -> dict:
    return {
        "@type": "ItemList",
        "name": _JOBS_HEADLINE,
        "url": f"{site_url}/jobs",
        "numberOfItems": len(jobs),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": j.title,
                "url": f"{site_url}/jobs/{j.id}",
            }
            for i, j in enumerate(jobs[:10])
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML rendering
# ─────────────────────────────────────────────────────────────────────────────


def _encode_jsonld(graph: list[dict]) -> str:
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


def _render_page(
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
    jsonld = _encode_jsonld(graph)

    truncated = description
    if len(truncated) > _OG_DESCRIPTION_LIMIT:
        truncated = truncated[: _OG_DESCRIPTION_LIMIT - 1].rstrip() + "…"

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


def _site_nav_html(site_url: str) -> str:
    e = html.escape
    return (
        '<nav aria-label="ניווט ראשי">\n'
        "  <ul>\n"
        f'    <li><a href="{e(site_url)}/">{e(SITE_NAME)}</a></li>\n'
        f'    <li><a href="{e(site_url)}/jobs">{e(_JOBS_HEADLINE)}</a></li>\n'
        "  </ul>\n"
        "</nav>\n"
    )


def _format_salary(min_v: int | None, max_v: int | None) -> str | None:
    if not min_v and not max_v:
        return None
    if min_v and max_v:
        return f"{min_v:,} – {max_v:,} ₪ לחודש"
    if min_v:
        return f"החל מ-{min_v:,} ₪ לחודש"
    return f"עד {max_v:,} ₪ לחודש"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/api/og/home", response_class=HTMLResponse, include_in_schema=False)
async def og_home(
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Server-rendered landing page for crawlers."""
    site_url = settings.frontend_base_url
    title = f"{_HOME_HEADLINE} — {SITE_NAME}"

    result = await session.execute(
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
        .order_by(Job.is_featured.desc(), Job.created_at.desc())  # pyright: ignore[reportAttributeAccessIssue]
        .limit(6)
    )
    featured = list(result.scalars().all())

    e = html.escape
    items = "".join(
        f'  <li><a href="{e(site_url)}/jobs/{j.id}">'
        f"<strong>{e(j.title)}</strong> — {e(j.location)}</a></li>\n"
        for j in featured
    )
    body_html = (
        f"<header>\n  <h1>{e(_HOME_HEADLINE)}</h1>\n"
        f"  <p>{e(_HOME_DESCRIPTION)}</p>\n</header>\n"
        f"{_site_nav_html(site_url)}"
        f'<section aria-label="משרות נבחרות">\n'
        f"  <h2>משרות נבחרות</h2>\n"
        f"  <ul>\n{items}  </ul>\n"
        f'  <p><a href="{e(site_url)}/jobs">לכל המשרות</a></p>\n'
        f"</section>\n"
    )

    return _render_page(
        title=title,
        description=_HOME_DESCRIPTION,
        canonical=f"{site_url}/",
        og_type="website",
        body_html=body_html,
        graph=_site_jsonld(site_url),
    )


@router.get("/api/og/jobs", response_class=HTMLResponse, include_in_schema=False)
async def og_jobs_index(
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Server-rendered job board for crawlers."""
    site_url = settings.frontend_base_url
    title = f"{_JOBS_HEADLINE} — {SITE_NAME}"

    result = await session.execute(
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
        .order_by(Job.is_featured.desc(), Job.created_at.desc())  # pyright: ignore[reportAttributeAccessIssue]
        .limit(_JOBS_INDEX_LIMIT)
    )
    jobs = list(result.scalars().all())

    e = html.escape
    items = []
    for j in jobs:
        salary = _format_salary(j.salary_min, j.salary_max)
        salary_html = f"      <span>{e(salary)}</span>\n" if salary else ""
        items.append(
            f'    <li>\n      <a href="{e(site_url)}/jobs/{j.id}">'
            f"<strong>{e(j.title)}</strong></a>\n"
            f"      <span>{e(j.location)}</span>\n"
            f"{salary_html}"
            f"    </li>\n"
        )
    list_html = "".join(items) or "    <li>אין כרגע משרות פתוחות.</li>\n"

    body_html = (
        f"<header>\n  <h1>{e(_JOBS_HEADLINE)}</h1>\n"
        f"  <p>{e(_JOBS_DESCRIPTION)}</p>\n</header>\n"
        f"{_site_nav_html(site_url)}"
        f'<section aria-label="רשימת משרות">\n'
        f"  <ul>\n{list_html}  </ul>\n"
        f"</section>\n"
    )

    graph: list[dict] = [
        _breadcrumb_jsonld(
            [(SITE_NAME, site_url), (_JOBS_HEADLINE, f"{site_url}/jobs")]
        )
    ]
    if jobs:
        graph.append(_itemlist_jsonld(jobs, site_url))

    return _render_page(
        title=title,
        description=_JOBS_DESCRIPTION,
        canonical=f"{site_url}/jobs",
        og_type="website",
        body_html=body_html,
        graph=graph,
    )


@router.get(
    "/api/og/jobs/{job_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def og_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Server-rendered job-detail page for crawlers.

    nginx routes /jobs/:id here for social scrapers (LinkedIn, WhatsApp, …)
    and search-engine crawlers (Googlebot). Real browsers fall through to
    the SPA.
    """
    job = (
        await session.execute(
            select(Job).where(Job.id == job_id, Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    site_url = settings.frontend_base_url
    canonical = f"{site_url}/jobs/{job.id}"
    description = job.description.strip().replace("\n", " ")
    title = f"{job.title} — {SITE_NAME}"

    e = html.escape
    salary = _format_salary(job.salary_min, job.salary_max)
    requirements_html = "".join(
        f"    <li>{e(req['text'])}</li>\n"
        for req in job.requirements
        if isinstance(req, dict) and req.get("text")
    )
    description_paragraphs = "".join(
        f"  <p>{e(p.strip())}</p>\n" for p in job.description.split("\n\n") if p.strip()
    )

    body_html = (
        f"<header>\n  <h1>{e(job.title)}</h1>\n"
        f"  <p><strong>מיקום:</strong> {e(job.location)}</p>\n"
        + (f"  <p><strong>שכר:</strong> {e(salary)}</p>\n" if salary else "")
        + "</header>\n"
        + _site_nav_html(site_url)
        + '<section aria-label="תיאור המשרה">\n  <h2>תיאור המשרה</h2>\n'
        + description_paragraphs
        + "</section>\n"
        + (
            '<section aria-label="דרישות התפקיד">\n  <h2>דרישות התפקיד</h2>\n'
            f"  <ul>\n{requirements_html}  </ul>\n</section>\n"
            if requirements_html
            else ""
        )
        + f'<p><a href="{e(canonical)}/apply">להגיש מועמדות</a></p>\n'
    )

    graph: list[dict] = [
        _build_job_posting_jsonld(job, site_url),
        _breadcrumb_jsonld(
            [
                (SITE_NAME, site_url),
                (_JOBS_HEADLINE, f"{site_url}/jobs"),
                (job.title, canonical),
            ]
        ),
    ]

    return _render_page(
        title=title,
        description=description,
        canonical=canonical,
        og_type="article",
        body_html=body_html,
        graph=graph,
    )
