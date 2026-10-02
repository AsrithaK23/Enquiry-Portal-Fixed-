import email
import imaplib
import os
import re
from email.header import decode_header
from email.utils import parseaddr
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

REQUIRED_MAIL_SETTINGS = ("IMAP_HOST", "IMAP_USERNAME", "IMAP_PASSWORD")


def send_login_otp(to_email, otp):
    domain = to_email.rsplit("@", 1)[-1].strip().rstrip(".")
    try:
        import dns.resolver
    except ImportError:
        # Keep mail usable if dependencies have not yet been reinstalled; SMTP still
        # performs recipient validation when the configured provider supports it.
        dns = None
    if dns:
        try:
            try:
                dns.resolver.resolve(domain, "MX", lifetime=3)
            except dns.resolver.NoAnswer:
                # RFC fallback: a domain without MX may receive mail via its A/AAAA record.
                try:
                    dns.resolver.resolve(domain, "A", lifetime=3)
                except dns.resolver.NoAnswer:
                    dns.resolver.resolve(domain, "AAAA", lifetime=3)
        except dns.resolver.NXDOMAIN as exc:
            raise RuntimeError("The email domain does not exist. Check the address and try again.") from exc
        except (dns.resolver.NoNameservers, dns.resolver.NoAnswer) as exc:
            raise RuntimeError("The email domain cannot receive mail. Check the address and try again.") from exc
        except dns.exception.Timeout:
            # DNS timeouts are transient; let SMTP make the final delivery decision.
            pass

    username = os.getenv("SMTP_USERNAME") or os.getenv("IMAP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD") or os.getenv("IMAP_PASSWORD", "").strip()
    missing = [label for label, value in (("SMTP username", username), ("SMTP password", password)) if not value]
    if missing:
        raise RuntimeError("Email verification is not configured. Add SMTP_USERNAME and SMTP_PASSWORD (or IMAP_USERNAME and IMAP_PASSWORD) to poc/backend/.env.")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    msg = MIMEText(f"Your Enquiry Portal login verification code is {otp}. It expires in 10 minutes.")
    msg["Subject"] = "Your Enquiry Portal verification code"
    msg["From"] = username
    msg["To"] = to_email
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            refused = server.sendmail(username, [to_email], msg.as_string())
            if to_email in refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    except smtplib.SMTPRecipientsRefused as exc:
        raise RuntimeError("This email address was rejected by the mail server. Check that it is correct and try again.") from exc
    except Exception as exc:
        raise RuntimeError("Could not send the verification email. Check your SMTP settings and try again.") from exc


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
                "in_reply_to": _decode(message.get("In-Reply-To")),
                "references": _decode(message.get("References")),
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

def send_reply(to_email: str, subject: str, body: str, in_reply_to: str = None, references: str = None) -> dict:
    """
    Sends the drafted reply via SMTP.
    Attaches RFC In-Reply-To and References headers to maintain the email thread.
    Returns {"sent": True, "message_id": "..."} or {"sent": False, "error": "..."}
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

    clean_subject = (subject or "Your enquiry").strip()
    if not re.match(r"^re\s*:\s*", clean_subject, flags=re.IGNORECASE):
        clean_subject = f"Re: {clean_subject}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = clean_subject
    msg["From"]    = username
    msg["To"]      = to_email

    # Generate RFC message ID
    domain = username.split("@")[-1] if "@" in username else "smart-enquiry-portal"
    generated_msg_id = f"<{uuid.uuid4()}@{domain}>"
    msg["Message-ID"] = generated_msg_id

    # Attach thread headers if replying to a known inbound email
    if in_reply_to:
        in_reply_to_clean = in_reply_to.strip()
        if not in_reply_to_clean.startswith("<") and in_reply_to_clean:
            in_reply_to_clean = f"<{in_reply_to_clean}>"
        msg["In-Reply-To"] = in_reply_to_clean

        # Build References chain
        ref_parts = []
        if references:
            ref_parts.extend(re.findall(r"<[^>]+>", references))
        if in_reply_to_clean not in ref_parts:
            ref_parts.append(in_reply_to_clean)
        msg["References"] = " ".join(ref_parts)

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(username, to_email, msg.as_string())
        return {"sent": True, "message_id": generated_msg_id}
    except Exception as e:
        return {"sent": False, "error": str(e)}
