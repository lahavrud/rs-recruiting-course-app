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
HOME_TITLE = "RS Recruiting — גיוס ניהול ותפעול נכסים"
HOME_HEADLINE = "גיוס לתפקידי ניהול ותפעול מבנים ונכסים"
HOME_DESCRIPTION = (
    "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול מבנים ונכסים. "
    "חיפוש עבודה עם ליווי אישי ושיבוץ מדויק."
)
JOBS_TITLE = "RS Recruiting — משרות פתוחות"
JOBS_HEADLINE = "משרות בתחום ניהול ותפעול מבנים"
JOBS_DESCRIPTION = (
    "כל המשרות הפתוחות בתחום ניהול ותפעול נכסים ומבנים — "
    "תפקידי ניהול, תפעול, אחזקה, בנייה, נדל״ן ועוד."
)

# /articles — mirrors ArticlesIndexPage.tsx PAGE_TITLE / PAGE_DESCRIPTION.
ARTICLES_TITLE = "RS Recruiting — מאמרים ומדריכים"
ARTICLES_HEADLINE = "מאמרים ומדריכים"
ARTICLES_DESCRIPTION = (
    "מדריכים, ניתוחי שוק וטיפים לתפקידים בתחום ניהול ותפעול מבנים ונכסים בישראל."
)

# /about — mirrors frontend/src/locales/he.json `about.*`.
ABOUT_TITLE = "RS Recruiting — אודות"
ABOUT_DESCRIPTION = (
    "הכירו את RS Recruiting — משרד גיוס והשמה בוטיקי המתמחה בניהול ותפעול נכסים ומבנים."
)
ABOUT_HEADLINE = "גיוס שמרגיש אחרת"
ABOUT_STORY_PARAGRAPHS = (
    "אנחנו לא מאמינים שגיוס טוב מתחיל בכמות קורות חיים. הוא מתחיל בשיחה — "
    "בהכרת האדם, הניסיון שלו, וסוג הסביבה שבה הוא פורח.",
    "RS Recruiting הוקם מתוך הבנה שתחום ניהול ותפעול נכסים ומבנים הוא עולם "
    "מקצועי עם שפה, אתגרים וציפיות מאוד ספציפיות. ידע ענפי אמיתי הוא ההבדל "
    "בין התאמה לפגיעה.",
)
ABOUT_VALUES = (
    (
        "מומחיות ענפית",
        "שנות ניסיון בתחום ניהול ותפעול נכסים ומבנים. מדברים את השפה של "
        "המגזר ומבינים מה מעסיקים באמת צריכים.",
    ),
    (
        "תהליך מכוון",
        "כל גיוס מתחיל מהבנה מעמיקה של הצורך. לא מחפשים מי שפנוי — "
        "מחפשים מי שנכון לתפקיד.",
    ),
    (
        "ליווי מלא",
        "נוכחים ממפגש ראשון ועד סגירת ההצעה. עם המעסיק ועם המועמד, יד ביד.",
    ),
)
ABOUT_PROCESS_STEPS = (
    (
        "שלחו קורות חיים",
        "שלחו את קורות החיים שלכם דרך הפלטפורמה ותקבלו אישור קבלה תוך זמן קצר.",
    ),
    (
        "מיון ותיאום אישי",
        "נקיים שיחת היכרות, נבין את הניסיון שלכם ונתאים בין צרכיכם למשרות הרלוונטיות.",
    ),
    (
        "ליווי עד לגיוס",
        "נלווה אתכם לאורך כל הדרך — הכנה לראיונות, משוב שוטף וסגירת ההצעה.",
    ),
)

# /contact — mirrors `contact.*`.
CONTACT_TITLE = "צרו קשר — RS Recruiting"
CONTACT_DESCRIPTION = (
    "צרו קשר עם RS Recruiting — משרד גיוס והשמה בוטיקי. נשמח לשמוע מכם."
)
CONTACT_HEADLINE = "נשמח לשמוע מכם"
CONTACT_SUBTITLE = "מעסיקים שמחפשים מועמדים, או מועמדים שרוצים לשמוע עוד — פנו אלינו."
CONTACT_EMAIL = "support@rs-recruiting.com"
