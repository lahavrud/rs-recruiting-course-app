"""
Local debug SMTP server — captures all emails and saves them to tmp/emails/.

Run with: uv run python scripts/smtp_debug.py

Listens on localhost:1025 (no auth, no TLS).
Configure .env: SMTP_HOST=localhost SMTP_PORT=1025 SMTP_USE_TLS=false

Each email is saved as:
  tmp/emails/<timestamp>-<to>/
    message.eml       <- open in Thunderbird / Apple Mail / Outlook for full rendering
    body.html         <- open directly in a browser (HTML emails)
    body.txt          <- plain text fallback
    <filename>.pdf    <- attachments (e.g. signed contract PDF)

Alternatively, use Mailpit for a browser-based UI (see README note at bottom).
"""

import asyncio
import email as email_lib
import re
from datetime import datetime
from email.message import Message
from pathlib import Path

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session

SAVE_DIR = Path("tmp/emails")


def _slug(text: str) -> str:
    return re.sub(r"[^\w@._-]", "_", text)[:40]


def _save_email(envelope: Envelope) -> Path:
    msg: Message = email_lib.message_from_bytes(envelope.content)  # type: ignore[arg-type]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    to_slug = _slug(", ".join(envelope.rcpt_tos))
    folder = SAVE_DIR / f"{ts}-{to_slug}"
    folder.mkdir(parents=True, exist_ok=True)

    # Save raw .eml (open in any mail client for full rendering)
    (folder / "message.eml").write_bytes(envelope.content)  # type: ignore[arg-type]

    # Walk MIME parts and save each
    saved: list[str] = []
    for part in msg.walk():
        ct = part.get_content_type()
        disp = part.get_content_disposition() or ""
        filename = part.get_filename()

        if ct == "text/html" and not filename:
            payload = part.get_payload(decode=True)
            if payload:
                (folder / "body.html").write_bytes(payload)
                saved.append("body.html")

        elif ct == "text/plain" and not filename:
            payload = part.get_payload(decode=True)
            if payload:
                (folder / "body.txt").write_bytes(payload)
                saved.append("body.txt")

        elif disp == "attachment" and filename:
            safe_name = re.sub(r"[^\w.\-]", "_", filename)
            payload = part.get_payload(decode=True)
            if payload:
                (folder / safe_name).write_bytes(payload)
                saved.append(safe_name)

    return folder, msg, saved


class CapturingHandler:
    async def handle_DATA(
        self, server: SMTP, session: Session, envelope: Envelope
    ) -> str:
        folder, msg, saved = _save_email(envelope)

        print("\n" + "─" * 60)
        print(f"  From:    {envelope.mail_from}")
        print(f"  To:      {', '.join(envelope.rcpt_tos)}")
        print(f"  Subject: {msg.get('Subject', '(no subject)')}")
        print(f"  Saved →  {folder}/")
        for f in saved:
            abs_path = (folder / f).resolve()
            if f.endswith(".html"):
                print(f"           open in browser: file://{abs_path}")
            else:
                print(f"           {abs_path}")
        print("─" * 60)

        return "250 Message accepted"


async def main() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    handler = CapturingHandler()
    controller = Controller(handler, hostname="0.0.0.0", port=1025)
    controller.start()
    print("Debug SMTP server running on 0.0.0.0:1025 — press Ctrl+C to stop")
    print(f"Emails saved to: {SAVE_DIR.resolve()}/")
    print()
    print("TIP: For a browser UI with full HTML preview, run Mailpit instead:")
    print("  docker run -d -p 1025:1025 -p 8025:8025 --name mailpit axllent/mailpit")
    print("  Then open http://localhost:8025")
    print()
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        print("\nSMTP server stopped.")


if __name__ == "__main__":
    asyncio.run(main())
