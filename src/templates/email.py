"""HTML email templates for RS Recruiting transactional emails.

Brand: dark luxury boutique. Minimal surfaces, warm metallic accents.
Color references match the Tailwind token system in index.css.
"""

import base64 as _b64
import html as _html
from pathlib import Path as _Path

from src.core.infrastructure.config import settings as _settings

_e = _html.escape

# Dark surfaces
_VOID = "#0D0B09"  # outer background
_CARD = "#1A1816"  # card surface
_WELL = "#141210"  # sunken / header band
_BORDER = "#302C28"  # white/8 equivalent

# Brand metals
_COPPER = "#B87333"
_GOLD = "#C9A84C"

# Text
_TEXT_HI = "#E0DCDB"
_TEXT_MID = "#999693"
_TEXT_LO = "#6B6866"

_LOGO_B64 = _b64.b64encode(
    (_Path(__file__).parent.parent / "assets" / "rs-logo-email.svg").read_bytes()
).decode()

_BASE = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:{void};
             font-family:Georgia,'Times New Roman',serif;direction:rtl;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:{void};padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:{card};border-radius:4px;
                      border:1px solid {border};
                      max-width:520px;width:100%;
                      overflow:hidden;">

          <!-- header band — dir=ltr forces logo to physical left in RTL email -->
          <tr>
            <td bgcolor="{well}" dir="ltr"
                style="background:{well};padding:16px 36px;
                       border-bottom:1px solid {border};">
              <table cellpadding="0" cellspacing="0" dir="ltr">
                <tr>
                  <td style="vertical-align:middle;padding-right:12px;width:40px;">
                    {logo_img_tag}
                  </td>
                  <td style="vertical-align:middle;">
                    <span style="font-size:11px;font-weight:600;letter-spacing:4px;
                                 text-transform:uppercase;color:{copper};
                                 font-family:Arial,sans-serif;">RS Recruiting</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- body -->
          <tr>
            <td style="padding:36px;">
              {body_html}
            </td>
          </tr>

          <!-- footer -->
          <tr>
            <td style="padding:20px 36px;border-top:1px solid {border};">
              <p style="margin:0;font-size:11px;letter-spacing:1px;
                        color:{lo};">
                <a href="mailto:support@rs-recruiting.com"
                   style="color:{lo};text-decoration:none;">support@rs-recruiting.com</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _logo_img_tag() -> str:
    if _settings.logo_public_url:
        src = _settings.logo_public_url
    else:
        src = f"data:image/svg+xml;base64,{_LOGO_B64}"
    return (
        f'<img src="{src}" alt="RS" width="40" height="40"'
        f' style="display:block;width:40px;height:40px;">'
    )


def _wrap(subject: str, body_html: str) -> str:
    return _BASE.format(
        subject=subject,
        void=_VOID,
        card=_CARD,
        well=_WELL,
        border=_BORDER,
        copper=_COPPER,
        lo=_TEXT_LO,
        logo_img_tag=_logo_img_tag(),
        body_html=body_html,
    )


def _cta(url: str, label: str) -> str:
    return (
        f'<table cellpadding="0" cellspacing="0" style="margin:32px 0 0;">'
        f"<tr><td>"
        f'<a href="{url}" target="_blank"'
        f'   style="display:inline-block;background:{_COPPER};'
        f"          color:#ffffff;text-decoration:none;"
        f"          font-family:Arial,sans-serif;font-size:13px;"
        f"          font-weight:600;letter-spacing:1px;"
        f'          padding:14px 28px;border-radius:2px;">'
        f"{label}"
        f"</a>"
        f"</td></tr></table>"
    )


def _h(text: str) -> str:
    return (
        f'<h2 style="margin:0 0 20px;font-size:22px;font-weight:400;'
        f'color:{_TEXT_HI};line-height:1.3;">{text}</h2>'
    )


def _p(text: str, muted: bool = False) -> str:
    color = _TEXT_MID if muted else _TEXT_HI
    return (
        f'<p style="margin:0 0 14px;font-family:Arial,sans-serif;'
        f'font-size:14px;line-height:1.7;color:{color};">{text}</p>'
    )


def _rule() -> str:
    return f'<div style="border-top:1px solid {_BORDER};margin:28px 0;"></div>'


def build_invite_html(registration_url: str, contact_name: str | None = None) -> str:
    """HTML invite email sent to companies when admin creates an invite."""
    safe_name = _e(contact_name) if contact_name else None
    greeting = f"שלום {safe_name}," if safe_name else "שלום,"
    body = (
        _h("הזמנה להצטרפות לפלטפורמה")
        + _p(greeting)
        + _p("הוזמנת להירשם לפלטפורמת RS Recruiting ולהתחיל לפרסם משרות ולקבל מועמדים.")
        + _cta(registration_url, "השלמת תהליך ההרשמה")
        + _rule()
        + _p("הקישור תקף ל-48 שעות בלבד.", muted=True)
    )
    return _wrap("הזמנה להרשמה — RS Recruiting", body)


def build_approval_html(company_name: str, activation_url: str) -> str:
    """HTML approval email sent after admin approves a company registration."""
    safe_company = _e(company_name)
    body = (
        _h("הבקשה שלכם אושרה")
        + _p(f"בקשת ההרשמה של <strong>{safe_company}</strong> התקבלה.")
        + _p(
            "מצורף לאימייל זה החוזה החתום. "
            "לחצו על הכפתור להפעלת החשבון ותחילת השימוש בפלטפורמה."
        )
        + _cta(activation_url, "הפעלת החשבון")
        + _rule()
        + _p("לאחר הלחיצה תוכלו להתחבר ולהתחיל לפרסם משרות.", muted=True)
    )
    return _wrap("הבקשה שלכם אושרה — RS Recruiting", body)


def build_rejection_html(company_name: str) -> str:
    """HTML rejection email sent when admin rejects a company registration."""
    safe_company = _e(company_name)
    body = (
        _h("בקשת ההרשמה נדחתה")
        + _p(f"בקשת ההרשמה של <strong>{safe_company}</strong> לא אושרה.")
        + _p(
            "אם אתם סבורים שמדובר בטעות, אנא צרו קשר עם צוות RS Recruiting.",
            muted=True,
        )
    )
    return _wrap("עדכון בנושא בקשת ההרשמה — RS Recruiting", body)


def build_new_registration_html(
    company_name: str,
    company_id: str,
    address: str,
    contact_name: str,
    email: str,
    mobile: str,
    admin_url: str,
) -> str:
    """HTML notification sent to admins when a new company registers."""
    sc, sid, saddr = _e(company_name), _e(company_id), _e(address)
    scontact, semail, smobile = _e(contact_name), _e(email), _e(mobile)
    body = (
        _h("חברה חדשה ממתינה לאישור")
        + _p(f"<strong>{sc}</strong> השלימה את תהליך ההרשמה.")
        + _rule()
        + _p(f"שם חברה: <strong>{sc}</strong>")
        + _p(f"ח.פ: {sid}")
        + _p(f"כתובת: {saddr}")
        + _p(f"איש קשר: {scontact}")
        + _p(f'דוא"ל: {semail}')
        + _p(f"נייד: {smobile}")
        + _cta(admin_url, "מעבר לניהול חברות")
    )
    return _wrap("בקשת הרשמה חדשה — RS Recruiting", body)


def build_new_job_html(
    job_title: str,
    company_name: str,
    location: str,
    job_id: int,
    admin_url: str,
) -> str:
    """HTML notification sent to admins when a new job is submitted for approval."""
    stitle = _e(job_title)
    scompany = _e(company_name)
    slocation = _e(location)
    body = (
        _h("משרה חדשה ממתינה לאישור")
        + _rule()
        + _p(f"כותרת: <strong>{stitle}</strong>")
        + _p(f"חברה: {scompany}")
        + _p(f"מיקום: {slocation}")
        + _p(f"מזהה משרה: #{job_id}")
        + _cta(admin_url, "מעבר לניהול משרות")
    )
    return _wrap("משרה חדשה לאישור — RS Recruiting", body)


def build_job_updated_html(
    job_title: str,
    company_name: str,
    location: str,
    job_id: int,
    status: str,
    admin_url: str,
) -> str:
    """HTML notification sent to admins when a job posting is updated."""
    stitle = _e(job_title)
    scompany = _e(company_name)
    slocation = _e(location)
    sstatus = _e(status)
    body = (
        _h("פרסום משרה עודכן")
        + _rule()
        + _p(f"כותרת: <strong>{stitle}</strong>")
        + _p(f"חברה: {scompany}")
        + _p(f"מיקום: {slocation}")
        + _p(f"מזהה משרה: #{job_id}")
        + _p(f"סטטוס: {sstatus}")
        + _cta(admin_url, "מעבר לניהול משרות")
    )
    return _wrap("עדכון פרסום משרה — RS Recruiting", body)


def build_application_status_candidate_html(
    candidate_name: str,
    job_title: str,
    old_status: str,
    new_status: str,
    notes: str | None,
) -> str:
    """HTML status update email sent to the candidate."""
    sname = _e(candidate_name)
    stitle = _e(job_title)
    sold = _e(old_status)
    snew = _e(new_status)
    snotes = _e(notes) if notes else None
    body = (
        _h("עדכון סטטוס מועמדות")
        + _p(f"שלום {sname},")
        + _p(f"סטטוס מועמדותך למשרת <strong>{stitle}</strong> עודכן.")
        + _rule()
        + _p(f"סטטוס קודם: {sold}")
        + _p(f"סטטוס חדש: <strong>{snew}</strong>")
        + (_p(f"הערות: {snotes}", muted=True) if snotes else "")
    )
    return _wrap(f"עדכון מועמדות — {stitle}", body)


def build_application_status_company_html(
    company_name: str,
    job_title: str,
    candidate_name: str,
    old_status: str,
    new_status: str,
    notes: str | None,
) -> str:
    """HTML status update email sent to the company."""
    scompany = _e(company_name)
    stitle = _e(job_title)
    scandidate = _e(candidate_name)
    sold = _e(old_status)
    snew = _e(new_status)
    snotes = _e(notes) if notes else None
    body = (
        _h("עדכון סטטוס מועמדות")
        + _p(f"שלום {scompany},")
        + _p(f"סטטוס מועמדות למשרת <strong>{stitle}</strong> עודכן.")
        + _rule()
        + _p(f"מועמד: {scandidate}")
        + _p(f"סטטוס קודם: {sold}")
        + _p(f"סטטוס חדש: <strong>{snew}</strong>")
        + (_p(f"הערות: {snotes}", muted=True) if snotes else "")
    )
    return _wrap(f"עדכון מועמדות — {stitle}", body)


def build_job_contact_html(
    job_title: str,
    company_name: str,
    admin_note: str,
) -> str:
    """HTML email sent by admin to a company regarding a specific job posting."""
    stitle = _e(job_title)
    scompany = _e(company_name)
    snote = _e(admin_note) if admin_note else ""
    body = (
        _h("פנייה ממנהל המערכת")
        + _p(f"שלום {scompany},")
        + _p(f"פנייה זו נשלחה בנוגע למשרת <strong>{stitle}</strong>.")
        + _rule()
        + (_p(snote) if snote else "")
        + _rule()
        + _p("לשאלות ופניות נוספות, אנא צרו קשר עם צוות RS Recruiting.", muted=True)
    )
    return _wrap("פנייה בנוגע למשרה — RS Recruiting", body)
