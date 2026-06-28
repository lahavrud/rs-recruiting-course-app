"""Load and parse the Hebrew SEO articles from frontend/src/content/articles.

The .md files are the canonical source for both the SPA (which loads them via
Vite's `import.meta.glob`) and the backend prerender (which reads them via
the path below). The backend Dockerfile copies the directory into the image
so the same content is available server-side at runtime.

Parsing happens once at module import. Articles are tiny and never change
without a redeploy, so eager load + dict lookup is correct and zero-cost
per request.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import markdown

# In the Docker image the articles are copied to /app/articles/ by Dockerfile.
# When the API is run from a dev checkout we fall back to the frontend dir.
# This module lives at <root>/services/api/rs_api/api/seo/_articles.py, so the
# repo root is six parents up (seo→api→rs_api→api→services→root).
_DOCKER_PATH = Path("/app/articles")
_REPO_PATH = (
    Path(__file__).resolve().parents[5] / "frontend" / "src" / "content" / "articles"
)
_ARTICLES_DIR = _DOCKER_PATH if _DOCKER_PATH.exists() else _REPO_PATH

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    description: str
    date: str  # ISO yyyy-mm-dd from frontmatter
    body_html: str
    image: str | None = None
    image_alt: str | None = None
    keywords: str | None = None


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Parse the YAML-ish `key: "value"` header used by the .md files."""
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = line.split(":", 1)
        if len(kv) != 2:
            continue
        key, val = kv[0].strip(), kv[1].strip()
        # Strip a single pair of surrounding double or single quotes.
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        meta[key] = val
    return meta, m.group(2)


def _load_one(path: Path) -> Article | None:
    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    if not all(k in meta and meta[k] for k in ("title", "description", "date")):
        # Drafts missing required metadata are skipped, matching the SPA loader.
        return None
    return Article(
        slug=meta.get("slug") or path.stem,
        title=meta["title"],
        description=meta["description"],
        date=meta["date"],
        body_html=markdown.markdown(body, extensions=["extra"]),
        image=meta.get("image") or None,
        image_alt=meta.get("imageAlt") or None,
        keywords=meta.get("keywords") or None,
    )


def _load_all() -> dict[str, Article]:
    if not _ARTICLES_DIR.exists():
        return {}
    loaded: list[Article] = []
    for path in sorted(_ARTICLES_DIR.glob("*.md")):
        article = _load_one(path)
        if article is not None:
            loaded.append(article)
    # Newest first — same order the SPA uses.
    loaded.sort(key=lambda a: a.date, reverse=True)
    return {a.slug: a for a in loaded}


_ARTICLES_BY_SLUG: dict[str, Article] = _load_all()


def get_article(slug: str) -> Article | None:
    return _ARTICLES_BY_SLUG.get(slug)


def list_articles() -> list[Article]:
    return list(_ARTICLES_BY_SLUG.values())
