"""robots.txt + sitemap.xml routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.enums import JobStatus
from src.models import Job

from ._content import DISALLOWED_PATHS

router = APIRouter()

_SITEMAP_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
_SITEMAP_FOOTER = "</urlset>"

# slug + lastmod for /articles sitemap entries. Sync when adding an article
# (bodies live in frontend/src/content/articles/*.md).
_ARTICLES = (
    ("mah-ze-nihul-mabnim", "2026-05-15"),
    ("madrich-raayon-nihul-nechasim", "2026-05-10"),
    ("sachar-nihul-nechasim-2026", "2026-05-05"),
)


def _url_entry(loc: str, lastmod: str | None = None, changefreq: str = "weekly") -> str:
    mod = f"  <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    freq = f"  <changefreq>{changefreq}</changefreq>\n"
    return f"  <url>\n  <loc>{loc}</loc>\n{mod}{freq}  </url>\n"


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt() -> str:
    sitemap_url = f"{settings.frontend_base_url}/sitemap.xml"
    disallow = "\n".join(f"Disallow: {p}" for p in DISALLOWED_PATHS)
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
    entries += _url_entry(f"{base}/articles", changefreq="weekly")
    for slug, lastmod in _ARTICLES:
        entries += _url_entry(
            f"{base}/articles/{slug}", lastmod=lastmod, changefreq="monthly"
        )
    for job_id, updated_at in jobs:
        lastmod = updated_at.date().isoformat() if updated_at else today
        entries += _url_entry(f"{base}/jobs/{job_id}", lastmod=lastmod)

    return _SITEMAP_HEADER + entries + _SITEMAP_FOOTER
