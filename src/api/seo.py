"""SEO endpoints: /robots.txt, /sitemap.xml, and /api/og/jobs/{id}."""

import html
import json
from datetime import UTC, datetime

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

_SITEMAP_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
_SITEMAP_FOOTER = "</urlset>"


def _url_entry(loc: str, lastmod: str | None = None, changefreq: str = "weekly") -> str:
    mod = f"  <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    freq = f"  <changefreq>{changefreq}</changefreq>\n"
    return f"  <url>\n  <loc>{loc}</loc>\n{mod}{freq}  </url>\n"


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt() -> str:
    sitemap_url = f"{settings.frontend_base_url}/sitemap.xml"
    return f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n"


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


def _build_job_posting_jsonld(job: Job, site_url: str) -> dict:
    posting: dict = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": f"{job.description}\n\n{job.requirements}",
        "datePosted": job.created_at.isoformat(),
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


@router.get(
    "/api/og/jobs/{job_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def og_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """HTML response with job-specific <head> for non-JS social scrapers.

    nginx routes /jobs/:id here only when the User-Agent matches a known
    social-preview bot (LinkedIn, WhatsApp, Twitter, Slack, etc.). Real
    browsers still get the SPA — this endpoint only exists to give scrapers
    a fully-meta'd HTML document they can parse without executing JS.
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
    if len(description) > _OG_DESCRIPTION_LIMIT:
        description = description[: _OG_DESCRIPTION_LIMIT - 1].rstrip() + "…"
    title = f"{job.title} — {SITE_NAME}"
    og_image = f"{site_url}/hero-city.jpg"

    # html.escape covers attribute values. For the JSON-LD payload inside a
    # <script> block we must also escape `<`, `>`, and `&` to unicode escapes —
    # otherwise a job title containing "</script>" would break out of the
    # script element (HTML parsing rules differ inside <script>; json.dumps
    # alone is not enough).
    e = html.escape
    jsonld = (
        json.dumps(_build_job_posting_jsonld(job, site_url), ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

    body = (
        "<!doctype html>\n"
        '<html lang="he" dir="rtl">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        f"<title>{e(title)}</title>\n"
        f'<meta name="description" content="{e(description)}">\n'
        f'<link rel="canonical" href="{e(canonical)}">\n'
        f'<meta property="og:title" content="{e(title)}">\n'
        f'<meta property="og:description" content="{e(description)}">\n'
        '<meta property="og:type" content="article">\n'
        f'<meta property="og:site_name" content="{e(SITE_NAME)}">\n'
        f'<meta property="og:url" content="{e(canonical)}">\n'
        f'<meta property="og:image" content="{e(og_image)}">\n'
        '<meta property="og:locale" content="he_IL">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{e(title)}">\n'
        f'<meta name="twitter:description" content="{e(description)}">\n'
        f'<meta name="twitter:image" content="{e(og_image)}">\n'
        f'<script type="application/ld+json">{jsonld}</script>\n'
        "</head>\n"
        "<body></body>\n"
        "</html>\n"
    )
    # Scrapers re-fetch periodically; an hour of cache is plenty and keeps
    # job edits from being invisible for too long.
    return HTMLResponse(
        content=body,
        headers={"Cache-Control": "public, max-age=3600"},
    )
