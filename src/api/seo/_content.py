"""Constants and Hebrew copy used by the SEO prerender endpoints."""

SITE_NAME = "RS Recruiting"

# Description and twitter:description truncation limit (Google snippet length).
OG_DESCRIPTION_LIMIT = 160

# Cap on how many jobs we list in the prerendered job board for crawlers.
JOBS_INDEX_LIMIT = 50

# Google drops JobPostings from rich results after 6 months without an
# explicit validThrough. 90 days matches typical Israeli recruitment cadence —
# admins can refresh by editing the job (updated_at change → sitemap lastmod).
JOB_POSTING_VALID_DAYS = 90

# Routes that should never appear in search results: authenticated areas and
# auth flow pages. Public routes (/, /jobs, /jobs/:id) remain crawlable.
DISALLOWED_PATHS = (
    "/admin",
    "/admin/",
    "/company",
    "/company/",
    "/dashboard",
    "/activate",
    "/login",
    "/register",
)

# Hebrew copy for prerendered pages. Mirrors the SPA's `landing.seo.*` and
# `publicJobs.board.*` i18n keys — duplicated here because the prerender
# endpoints run server-side without access to the frontend's locale bundle.
# Keep in sync with frontend/src/locales/he.json when wording changes.
HOME_HEADLINE = "גיוס לתפקידי ניהול ותפעול מבנים ונכסים"
HOME_DESCRIPTION = (
    "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול מבנים ונכסים. "
    "חיפוש עבודה עם ליווי אישי ושיבוץ מדויק."
)
JOBS_HEADLINE = "משרות בתחום ניהול ותפעול מבנים"
JOBS_DESCRIPTION = (
    "כל המשרות הפתוחות בתחום ניהול ותפעול נכסים ומבנים — "
    "תפקידי ניהול, תפעול, אחזקה, בנייה, נדל״ן ועוד."
)
