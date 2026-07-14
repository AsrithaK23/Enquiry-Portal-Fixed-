from flask import Blueprint, request, jsonify
from database import db
from models import Client, Enquiry, ActivityLog
from services.ai_service import analyse
from services.email_service import fetch_unread_emails, send_reply, missing_mail_settings

email_bp = Blueprint("email_webhook", __name__)


def build_reply(client_name, enquiry_id, category, priority):
    return f"""Dear {client_name},

Thank you for reaching out to us.

We have received your enquiry and our team will get back to you shortly.

Reference information:
  Enquiry ID : #{enquiry_id}
  Category   : {category}
  Priority   : {priority}

If you need to follow up, please quote Enquiry #{enquiry_id} in your reply.

Best regards,
Enquiry Portal Team
"""


def create_enquiry_from_email(from_email: str, from_name: str, subject: str, body: str, source="Email"):
    """
    Shared logic: given raw email fields, finds/creates the client,
    runs AI classification, creates the Enquiry + ActivityLog, and
    returns (enquiry, client, is_new_client, reply_text).

    Used by BOTH the inbound webhook route and the IMAP inbox-poll route,
    so email creation behaves identically no matter which path mail comes in from.
    """
    from_email = (from_email or "").strip().lower()
    from_name = (from_name or "Unknown Sender").strip()
    subject = (subject or "").strip()
    body = (body or "").strip()

    full_text = f"{subject}. {body}" if subject else body
    ai = analyse(full_text)

    client = Client.query.filter_by(email=from_email).first()
    if not client:
        client = Client(name=from_name, email=from_email)
        db.session.add(client)
        db.session.flush()
        is_new = True
    else:
        is_new = False

    enq = Enquiry(
        client_id=client.id, customer_name=client.name, email=from_email,
        source=source, description=body,
        category=ai["category"], priority=ai["priority"],
        ai_summary=ai["ai_summary"], status="New",
    )
    db.session.add(enq)
    db.session.flush()
    db.session.add(ActivityLog(
        enquiry_id=enq.id,
        action=f"Enquiry auto-created from {source.lower()}. {'New client.' if is_new else 'Existing client.'} "
               f"Category: {enq.category}, Priority: {enq.priority}"
    ))
    db.session.commit()

    reply_text = build_reply(client.name, enq.id, enq.category, enq.priority)
    return enq, client, is_new, reply_text


@email_bp.route("/api/webhook/email", methods=["POST"])
def receive_email():
    """
    For EXTERNAL push sources (SendGrid inbound parse, Zapier, etc.)
    that POST already-parsed email JSON to this endpoint.
    This does NOT read your own mailbox — see /api/email/check-inbox for that.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    from_email = (data.get("from_email") or "").strip().lower()
    from_name  = (data.get("from_name")  or "Unknown Sender").strip()
    subject    = (data.get("subject")    or "").strip()
    body       = (data.get("body")       or "").strip()

    if not from_email or not body:
        return jsonify({"error": "from_email and body are required"}), 400

    enq, client, is_new, reply_text = create_enquiry_from_email(from_email, from_name, subject, body, source="Email")

    return jsonify({
        "success": True, "enquiry_id": enq.id, "client_id": client.id,
        "is_new_client": is_new, "category": enq.category, "priority": enq.priority,
        "reply_to": from_email, "reply_subject": f"Re: {subject} [Enquiry #{enq.id}]",
        "reply_body": reply_text,
    }), 200


@email_bp.route("/api/email/check-inbox", methods=["POST", "GET"])
def check_inbox():
    """
    THIS is the piece that was missing: actually connects to your IMAP
    mailbox (via services/email_service.fetch_unread_emails), creates an
    Enquiry for every unread email found, and optionally sends the
    auto-reply back.

    Call this:
      - manually (a "Check emails now" button in the dashboard hitting
        POST /api/email/check-inbox), or
      - on a schedule (a cron job / Windows Task Scheduler / hosting
        provider's scheduled task hitting this URL every few minutes).
    """
    missing = missing_mail_settings()
    if missing:
        return jsonify({
            "error": "Email intake is not configured.",
            "missing_env_vars": missing,
        }), 400

    try:
        emails = fetch_unread_emails(limit=10, mark_seen=True)
    except Exception as e:
        # Almost always: wrong host, wrong password (needs a Gmail App
        # Password, not your normal password), or IMAP not enabled on the account.
        return jsonify({"error": f"Could not connect to mailbox: {e}"}), 502

    created = []
    for msg in emails:
        enq, client, is_new, reply_text = create_enquiry_from_email(
            from_email=msg["sender_email"],
            from_name=msg["sender_name"],
            subject=msg["subject"],
            body=msg["body"],
            source="Email",
        )

        send_result = send_reply(
            to_email=msg["sender_email"],
            subject=msg["subject"],
            body=reply_text,
        )

        created.append({
            "enquiry_id": enq.id,
            "from": msg["sender_email"],
            "subject": msg["subject"],
            "is_new_client": is_new,
            "reply_sent": send_result.get("sent", False),
            "reply_error": send_result.get("error"),
        })

    return jsonify({
        "success": True,
        "checked": len(emails),
        "enquiries_created": len(created),
        "details": created,
    }), 200