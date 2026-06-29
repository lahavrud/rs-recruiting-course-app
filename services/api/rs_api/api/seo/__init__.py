"""SEO endpoints package.

Public surface is the FastAPI ``router``; ``rs_api.main`` registers it via
``app.include_router(seo.router)``. Internal modules split the implementation
to keep individual files under the project's 200-line cap.

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

from fastapi import APIRouter

from ._pages import router as _pages_router
from ._routes import router as _og_router
from ._sitemap import router as _sitemap_router

router = APIRouter()
router.include_router(_sitemap_router)
router.include_router(_og_router)
router.include_router(_pages_router)

__all__ = ["router"]
