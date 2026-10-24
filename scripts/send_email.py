"""Send email.txt (first line is 'Subject: ...') to yourself through Gmail SMTP."""
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
    if not user or not password:
        print("::warning::GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets not set; skipping email.")
        return

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
