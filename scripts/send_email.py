"""Send email.txt (first line is 'Subject: ...') to yourself through Gmail SMTP.

  python scripts/send_email.py          # send email.txt
  python scripts/send_email.py --test   # send a short test message instead
"""
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text())


def main():
    user = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    test = "--test" in sys.argv
    if not user or not password:
        if test:
            sys.exit("GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets are not set.")
        print("::warning::GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets not set; skipping email.")
        return

    if test:
        subject_line = "Subject: SeinBench: test email"
        body = (
            "This is a test from the SeinBench daily scout. If you're reading it, "
            "new-model notices will reach you.\n\n"
            f"Writers' Room: {CONFIG['site_url']}writers-room.html\n\n"
            "Nothing was generated and nothing was charged.\n"
        )
    else:
        subject_line, _, body = (ROOT / "email.txt").read_text().partition("\n")
    msg = EmailMessage()
    msg["Subject"] = subject_line.removeprefix("Subject: ")
    msg["From"] = f"SeinBench <{user}>"
    msg["To"] = CONFIG["email_to"]
    msg.set_content(body.lstrip("\n"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, password.replace(" ", ""))
        smtp.send_message(msg)
    print("Sent to", CONFIG["email_to"])


if __name__ == "__main__":
    sys.exit(main())
