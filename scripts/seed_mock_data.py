#!/usr/bin/env python3
"""הרצת נתוני בדיקה לפיתוח מקומי.

שימוש:
    PYTHONPATH=. uv run python scripts/seed_mock_data.py

הרץ לאחר הפעלת הבקאנד (docker compose up) והוספת משתמש מנהל.

יוצר:
    - 1 משתמש מנהל (admin@rsrecruit.com / Admin123!)
    - 3 חברות עם פרופילים
    - 15 משרות (5 לכל חברה, סטטוסים מעורבים)
    - 8 פרופילי מועמדים
    - כ-12 מועמדויות (סטטוסים שונים)
"""

import asyncio

from sqlalchemy import select

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import async_session, init_db
from src.core.infrastructure.security import get_password_hash
from src.core.services.storage_local import LocalStorageProvider
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.models import Application, CandidateProfile, CompanyProfile, Job, User

# Minimal valid single-page PDF used as a placeholder resume in seed data
_PLACEHOLDER_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000052 00000 n \n"
    b"0000000101 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n150\n%%EOF\n"
)

# ── מנהל ──
ADMIN_EMAIL = "admin@rsrecruit.com"
ADMIN_PASSWORD = "Admin123!"  # pragma: allowlist secret

# ── חברות ──
COMPANIES = [
    {
        "email": "ops@integrated-fm.com",
        "password": "Company123!",  # pragma: allowlist secret
        "company_name": 'פתרונות מתקנים בע"מ',
        "contact_person": "דוד כהן",
        "contact_phone": "050-1111111",
    },
    {
        "email": "hr@sharion.com",
        "password": "Company123!",  # pragma: allowlist secret
        "company_name": "שריון — אבטחה ותחזוקה",
        "contact_person": "נועה לוי",
        "contact_phone": "050-2222222",
    },
    {
        "email": "info@cleanpro.com",
        "password": "Company123!",  # pragma: allowlist secret
        "company_name": "קלינפרו שירותי מתקנים",
        "contact_person": "רן מזרחי",
        "contact_phone": "050-3333333",
    },
]

# ── משרות ──
JOBS_BY_COMPANY = [
    # פתרונות מתקנים
    [
        {
            "title": "מנהל מתקנים בכיר",
            "description": "ניהול קמפוס מסחרי — מיזוג, חשמל, אינסטלציה וניקיון.",
            "requirements": "5+ שנות ניסיון בניהול מתקנים. תואר הנדסה.",
            "location": "תל אביב",
            "salary_min": 18000,
            "salary_max": 25000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "טכנאי מיזוג אוויר",
            "description": "התקנה ותחזוקת מערכות מיזוג אצל לקוחות מגוונים.",
            "requirements": "3+ שנות ניסיון. תעודת מיזוג. רישיון נהיגה.",
            "location": "תל אביב",
            "salary_min": 12000,
            "salary_max": 17000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מהנדס מערכות בניין",
            "description": "ניהול מערכות BMS ואופטימיזציית צריכת אנרגיה.",
            "requirements": "תואר הנדסה מכנית/חשמלית. 3+ שנות ניסיון ב-BMS.",
            "location": "הרצליה",
            "salary_min": 15000,
            "salary_max": 22000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מנהל תחזוקה חשמלית",
            "description": "פיקוח על צוות חשמלאים ב-5 נכסי לקוח.",
            "requirements": "הנדסאי חשמל. 5+ שנות ניסיון. רישיון משרד האנרגיה.",
            "location": "תל אביב",
            "salary_min": 14000,
            "salary_max": 20000,
            "status": JobStatus.PENDING_APPROVAL,
        },
        {
            "title": "ראש צוות אינסטלציה",
            "description": "ניהול תחזוקת אינסטלציה בקמפוס בית חולים.",
            "requirements": "10+ שנות ניסיון. 3+ שנות ניהול. תעודת מים.",
            "location": "רמת גן",
            "salary_min": 16000,
            "salary_max": 22000,
            "status": JobStatus.CLOSED,
        },
    ],
    # שריון — אבטחה ותחזוקה
    [
        {
            "title": "מנהל מבצעי ביטחון",
            "description": "ניהול אבטחת 8 מבנים מסחריים ו-40 מאבטחים.",
            "requirements": "5+ שנות ניסיון. רישיון מנהל ביטחון ממשרד הפנים.",
            "location": "תל אביב",
            "salary_min": 18000,
            "salary_max": 24000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "רכז בטיחות אש",
            "description": "הטמעת תוכניות בטיחות אש ופיקוח על ציוד כיבוי.",
            "requirements": "תעודת בטיחות אש. 3+ שנות ניסיון. הדרכת עזרה ראשונה.",
            "location": "חיפה",
            "salary_min": 12000,
            "salary_max": 16000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "טכנאי בקרת כניסה",
            "description": "התקנת מערכות RFID, ביומטריה ואינטרקום.",
            "requirements": "2+ שנות ניסיון בבקרת כניסה. רקע אלקטרוניקה.",
            "location": "פתח תקווה",
            "salary_min": 10000,
            "salary_max": 14000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מאבטח — קמפוס היי-טק",
            "description": "סיורים, ניטור CCTV וקבלת אורחים בקמפוס טכנולוגי.",
            "requirements": "רישיון מאבטח בתוקף. עברית ואנגלית בסיסית.",
            "location": "הרצליה",
            "salary_min": 8000,
            "salary_max": 11000,
            "status": JobStatus.PENDING_APPROVAL,
        },
        {
            "title": "מנהל מערכות CCTV",
            "description": "ניהול Milestone XProtect, בריאות מצלמות ואחסון.",
            "requirements": "הסמכת Milestone. 3+ שנות ניסיון. זמינות כוננות.",
            "location": "תל אביב",
            "salary_min": 14000,
            "salary_max": 19000,
            "status": JobStatus.CLOSED,
        },
    ],
    # קלינפרו שירותי מתקנים
    [
        {
            "title": "מנהל פעילות ניקיון",
            "description": "ניהול ניקיון ב-12 נכסים וצוות של 80+ עובדים.",
            "requirements": "5+ שנות ניסיון בניהול ניקיון. שליטה בעברית ובערבית.",
            "location": "ירושלים",
            "salary_min": 16000,
            "salary_max": 22000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מומחה ניקיון תעשייתי",
            "description": "ניקיון מפעלי מזון ומחסנים. תפעול ציוד תעשייתי.",
            "requirements": "2+ שנות ניסיון. הסמכת חומרים מסוכנים.",
            "location": "אשדוד",
            "salary_min": 9000,
            "salary_max": 13000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מנהל פסולת ומיחזור",
            "description": "פיקוח על מיחזור ופינוי פסולת עבור לקוחות עסקיים.",
            "requirements": "3+ שנות ניסיון. ידע ברגולציית משרד הסביבה.",
            "location": "ראשון לציון",
            "salary_min": 11000,
            "salary_max": 16000,
            "status": JobStatus.PUBLISHED,
        },
        {
            "title": "מפקח איכות ניקיון",
            "description": "ביקורות איכות בלתי מוכרזות בכל אתרי הלקוחות.",
            "requirements": "2+ שנות ניסיון. עין חדה לפרטים. רכב פרטי.",
            "location": "תל אביב",
            "salary_min": 10000,
            "salary_max": 14000,
            "status": JobStatus.PENDING_APPROVAL,
        },
        {
            "title": "ראש צוות ניקיון",
            "description": "ניהול 6 עובדים בקומפלקס משרדי ממשלתי.",
            "requirements": "ניסיון ניהולי. אוריינות מחשב. אישור ביטחון.",
            "location": "ירושלים",
            "salary_min": 9000,
            "salary_max": 13000,
            "status": JobStatus.CLOSED,
        },
    ],
]

# ── מועמדים ──
CANDIDATES = [
    {
        "full_name": "אחמד פאהום",
        "email": "ahmed.fahoum@gmail.com",
        "phone": "054-1234567",
        "linkedin_url": "https://linkedin.com/in/ahmed-fahoum",
        "resume": True,
        "service_concept": (
            "שירות טוב הוא זמינות ועמידה בהתחייבויות. "
            "אני מאמין בתקשורת יזומה — לעדכן לפני שמבקשים."
        ),
        "salary_expectations": "18,000–22,000 ₪ לחודש",
        "personality_strength": "רגוע תחת לחץ ומאוד שיטתי",
        "personality_weakness": "לפעמים מרבה לעסוק בפרטים הקטנים",
    },
    {
        "full_name": "מאיה בן-דוד",
        "email": "maya.bd@gmail.com",
        "phone": "052-2345678",
        "linkedin_url": "https://linkedin.com/in/maya-ben-david",
        "resume": True,
        "service_concept": (
            "הלקוח צריך להרגיש שיש מישהו שאחראי. "
            "אני מגדירה ציפיות ברורות מהרגע הראשון ומעדכנת בכל שלב."
        ),
        "salary_expectations": "23,000–28,000 ₪ לחודש",
        "personality_strength": "מנהיגות חזקה ותיאום צוות",
        "personality_weakness": "נוטה לקחת על עצמה יותר מדי משימות",
    },
    {
        "full_name": "יוסי ממן",
        "email": "yossi.maman@gmail.com",
        "phone": "053-3456789",
        "linkedin_url": None,
        "resume": False,
        "service_concept": (
            "שירות טוב זה לעשות את העבודה נכון בפעם הראשונה. "
            "אני לא עוזב אתר עד שהדבר תוקן לגמרי."
        ),
        "salary_expectations": "12,000–15,000 ₪ לחודש",
        "personality_strength": "אמין, חרוץ, מצוין עם אנשים",
        "personality_weakness": "אנגלית מוגבלת",
    },
    {
        "full_name": "רינת שפירא",
        "email": "rinat.shapira@gmail.com",
        "phone": "050-4567890",
        "linkedin_url": "https://linkedin.com/in/rinat-shapira",
        "resume": True,
        "service_concept": (
            "שירות טוב מבוסס על סדר ומעקב. "
            "כל פנייה מקבלת מענה, כל הבטחה מתועדת ומקוימת."
        ),
        "salary_expectations": "16,000–20,000 ₪ לחודש",
        "personality_strength": "ארגון ותכנון מעולים",
        "personality_weakness": "לעיתים מתקשה להאציל משימות",
    },
    {
        "full_name": "שלמה אברהם",
        "email": "shlomo.avraham@gmail.com",
        "phone": "055-5678901",
        "linkedin_url": "https://linkedin.com/in/shlomo-avraham",
        "resume": True,
        "service_concept": (
            "מסביר ללקוח מה נעשה ולמה — לא רק מתקן ועוזב. "
            "אנשים צריכים להבין את הבעיה כדי לסמוך על הפתרון."
        ),
        "salary_expectations": "14,000–18,000 ₪ לחודש",
        "personality_strength": "פותר בעיות מעשי, לומד מהר",
        "personality_weakness": "מעדיף עבודה עצמאית על פני צוות גדול",
    },
    {
        "full_name": "ליאת אוחנה",
        "email": "liat.ohana@gmail.com",
        "phone": "052-6789012",
        "linkedin_url": None,
        "resume": False,
        "service_concept": (
            "כל פנייה — גם הקטנה ביותר — מקבלת יחס מכובד ומהיר. "
            "הרושם הראשוני הוא כל הביקור."
        ),
        "salary_expectations": "10,000–13,000 ₪ לחודש",
        "personality_strength": "ידידותית, מאורגנת, נוכחות טלפונית מצוינת",
        "personality_weakness": "אין רקע טכני",
    },
    {
        "full_name": "עמיר גולן",
        "email": "amir.golan@gmail.com",
        "phone": "054-7890123",
        "linkedin_url": "https://linkedin.com/in/amir-golan",
        "resume": True,
        "service_concept": (
            "שירות אמיתי הוא מניעת בעיות לפני שהן צצות. "
            "אני מעדיף תחזוקה מונעת על פני תיקון בשעת חירום."
        ),
        "salary_expectations": "25,000–32,000 ₪ לחודש",
        "personality_strength": "חשיבה אסטרטגית וידע טכני רחב",
        "personality_weakness": "חסר סבלנות לתהליכים איטיים",
    },
    {
        "full_name": "סאמי ג'בארין",
        "email": "sami.jabarin@gmail.com",
        "phone": "050-8901234",
        "linkedin_url": None,
        "resume": False,
        "service_concept": (
            "לקוח מרוצה מביא לקוח נוסף. אני עובד כאילו כל עבודה היא כרטיס הביקור שלי."
        ),
        "salary_expectations": "11,000–14,000 ₪ לחודש",
        "personality_strength": "עובד קשה ואמין ביותר",
        "personality_weakness": "השכלה פורמלית מוגבלת (כיתה י')",
    },
]


def _print_result(entity: str, action: str, detail: str = "") -> None:
    icon = "✅" if action == "created" else "⏭️"
    print(f"  {icon} {entity}: {detail}")


async def seed() -> None:
    """פונקציית הזרעה הראשית."""
    print("🌱 מזריע נתוני בדיקה עבור RS Recruiting\n")

    await init_db()

    async with async_session() as session:
        # ── מנהל ──
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if admin:
            _print_result("מנהל", "skipped", ADMIN_EMAIL)
            admin_user = admin
        else:
            admin_user = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_user)
            await session.flush()
            _print_result("מנהל", "created", f"{ADMIN_EMAIL} / {ADMIN_PASSWORD}")

        # ── חברות + משתמשים ──
        company_users: list[User] = []
        company_profiles: list[CompanyProfile] = []
        for c in COMPANIES:
            result = await session.execute(select(User).where(User.email == c["email"]))
            user = result.scalar_one_or_none()
            if user:
                _print_result("משתמש חברה", "skipped", c["email"])
            else:
                user = User(
                    email=c["email"],
                    hashed_password=get_password_hash(c["password"]),
                    role=UserRole.COMPANY,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                _print_result(
                    "משתמש חברה", "created", f"{c['email']} / {c['password']}"
                )

            result = await session.execute(
                select(CompanyProfile).where(CompanyProfile.user_id == user.id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                _print_result("פרופיל חברה", "skipped", c["company_name"])
            else:
                profile = CompanyProfile(
                    user_id=user.id,
                    name=c["company_name"],
                    contact_person=c["contact_person"],
                    contact_phone=c["contact_phone"],
                )
                session.add(profile)
                await session.flush()
                _print_result("פרופיל חברה", "created", c["company_name"])

            company_users.append(user)
            company_profiles.append(profile)

        # ── משרות ──
        all_jobs: list[Job] = []
        for idx, jobs in enumerate(JOBS_BY_COMPANY):
            profile = company_profiles[idx]
            for j in jobs:
                result = await session.execute(
                    select(Job).where(
                        Job.company_id == profile.id,
                        Job.title == j["title"],
                    )
                )
                job = result.scalar_one_or_none()
                if job:
                    _print_result("משרה", "skipped", f"{j['title']} ({profile.name})")
                else:
                    job = Job(
                        company_id=profile.id,
                        title=j["title"],
                        description=j["description"],
                        requirements=j["requirements"],
                        location=j["location"],
                        status=j["status"],
                    )
                    session.add(job)
                    await session.flush()
                    _print_result(
                        "משרה", "created", f"{j['title']} ({j['status'].value})"
                    )
                all_jobs.append(job)

        # ── מועמדים ──
        storage = LocalStorageProvider(storage_path=settings.local_storage_path)
        created_candidates: list[CandidateProfile] = []
        for cand in CANDIDATES:
            result = await session.execute(
                select(CandidateProfile).where(CandidateProfile.email == cand["email"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                _print_result("מועמד", "skipped", cand["full_name"])
                created_candidates.append(existing)
            else:
                resume_path: str | None = None
                if cand["resume"]:
                    file_name = (
                        cand["full_name"].replace(" ", "_").replace("'", "") + ".pdf"
                    )
                    resume_path = await storage.upload_file(
                        _PLACEHOLDER_PDF, file_name, "application/pdf"
                    )

                profile = CandidateProfile(
                    full_name=cand["full_name"],
                    email=cand["email"],
                    phone=cand["phone"],
                    linkedin_url=cand["linkedin_url"],
                    service_concept=cand["service_concept"],
                    salary_expectations=cand["salary_expectations"],
                    personality_strength=cand["personality_strength"],
                    personality_weakness=cand["personality_weakness"],
                )
                profile.resume_path = resume_path
                session.add(profile)
                await session.flush()
                _print_result("מועמד", "created", cand["full_name"])
                created_candidates.append(profile)

        # ── מועמדויות ──
        published_jobs = [j for j in all_jobs if j.status == JobStatus.PUBLISHED]
        statuses = [
            ApplicationStatus.NEW,
            ApplicationStatus.APPROVED_BY_ADMIN,
            ApplicationStatus.REJECTED,
            ApplicationStatus.HIRED,
        ]

        for i, candidate in enumerate(created_candidates):
            for offset in range(2):
                job_idx = (i + offset) % len(published_jobs)
                job = published_jobs[job_idx]

                result = await session.execute(
                    select(Application).where(
                        Application.job_id == job.id,
                        Application.candidate_id == candidate.id,
                    )
                )
                if result.scalar_one_or_none():
                    _print_result(
                        "מועמדות",
                        "skipped",
                        f"{candidate.full_name} → {job.title}",
                    )
                    continue

                app_status = statuses[(i + offset) % len(statuses)]
                admin_notes = None
                if app_status == ApplicationStatus.APPROVED_BY_ADMIN:
                    admin_notes = "מועמד מתאים, עם ניסיון רלוונטי. מאושר לראיון."
                elif app_status == ApplicationStatus.REJECTED:
                    admin_notes = "הניסיון אינו עומד בדרישות המינימום לתפקיד."
                elif app_status == ApplicationStatus.HIRED:
                    admin_notes = "התאמה מעולה. המועמד קיבל את ההצעה ואישר תחילת עבודה."

                app = Application(
                    job_id=job.id,
                    candidate_id=candidate.id,
                    status=app_status,
                    admin_notes=admin_notes,
                )
                session.add(app)
                await session.flush()
                _print_result(
                    "מועמדות",
                    "created",
                    f"{candidate.full_name} → {job.title} [{app_status.value}]",
                )

        await session.commit()

    print(f"\n{'─' * 50}")
    print(f"  {'סה"כ':<30} {'נוצר':>8} {'דולג':>8}")
    print(f"  {'─' * 46}")
    print(f"  {'מנהלים':<30} {'1':>8}")
    print(f"  {'חברות':<30} {'3':>8}")
    print(f"  {'משרות':<30} {'15':>8}")
    print(f"  {'מועמדים':<30} {'8':>8}")
    print(f"  {'מועמדויות':<30} {'~12–15':>8}")
    print(f"{'─' * 50}")
    print(f"\n🔑 כניסת מנהל:  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("🔑 כניסת חברה:  (כל חברה עם האימייל שלה / Company123!)")


def main() -> None:
    """נקודת כניסה."""
    asyncio.run(seed())


if __name__ == "__main__":
    main()
