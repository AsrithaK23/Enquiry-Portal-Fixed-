import email
import imaplib
import os
import re
from email.header import decode_header
from email.utils import parseaddr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

REQUIRED_MAIL_SETTINGS = ("IMAP_HOST", "IMAP_USERNAME", "IMAP_PASSWORD")


def missing_mail_settings():
    return [name for name in REQUIRED_MAIL_SETTINGS if not os.environ.get(name, "").strip()]


def _decode(value):
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _html_to_text(html):
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p\s*>", "\n", text)
    text = re.sub(r"(?s)<.*?>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _message_body(message):
    plain = ""
    html = ""

    if message.is_multipart():
        for part in message.walk():
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/plain" and not plain:
                plain = text
            elif content_type == "text/html" and not html:
                html = text
    else:
        payload = message.get_payload(decode=True)
        if payload:
            charset = message.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if message.get_content_type() == "text/html":
                html = text
            else:
                plain = text

    return (plain or _html_to_text(html)).strip()


def fetch_unread_emails(limit=10, mark_seen=False):
    host = os.environ.get("IMAP_HOST", "").strip()
    username = os.environ.get("IMAP_USERNAME", "").strip()
    password = os.environ.get("IMAP_PASSWORD", "").strip()
    folder = os.environ.get("IMAP_FOLDER", "INBOX").strip()

    missing = missing_mail_settings()
    if missing:
        raise RuntimeError(
            "Email intake is not configured. Add these values to poc/backend/.env: "
            + ", ".join(missing)
        )

    mailbox = imaplib.IMAP4_SSL(host)
    try:
        mailbox.login(username, password)
        mailbox.select(folder)
        _, data = mailbox.search(None, "UNSEEN")
        ids = data[0].split()[-limit:]
        emails = []

        for msg_id in ids:
            _, msg_data = mailbox.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            message = email.message_from_bytes(raw)
            sender_name, sender_email = parseaddr(_decode(message.get("From")))
            body = _message_body(message)
            emails.append({
                "message_id": message.get("Message-ID") or msg_id.decode(),
                "subject": _decode(message.get("Subject")) or "(no subject)",
                "sender_name": sender_name or sender_email or "Email Sender",
                "sender_email": sender_email,
                "body": body,
            })
            if not mark_seen:
                mailbox.store(msg_id, "-FLAGS", "\\Seen")

        return emails
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        mailbox.logout()

def send_reply(to_email: str, subject: str, body: str) -> dict:
    """
    Sends the drafted reply via SMTP.
    Returns {"sent": True} or {"sent": False, "error": "..."}
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    username   = os.getenv("IMAP_USERNAME")   # reuse same Gmail account
    password   = os.getenv("IMAP_PASSWORD")

    missing = [name for name in ("IMAP_USERNAME", "IMAP_PASSWORD") if not os.environ.get(name, "").strip()]
    if missing:
        return {
            "sent": False,
            "error": "Email sending is not configured. Add these values to poc/backend/.env: " + ", ".join(missing),
        }

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    msg["From"]    = username
    msg["To"]      = to_email

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(username, to_email, msg.as_string())
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}