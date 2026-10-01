from flask import Blueprint, request, jsonify
from database import db
from models import Client, Enquiry, ActivityLog, EmailLog
from datetime import datetime
import re
from services.ai_service import analyse, generate_followup_draft
from services.email_service import fetch_unread_emails, send_reply, missing_mail_settings
from services.thread_service import check_and_register_thread

email_bp = Blueprint("email_webhook", __name__)


def build_reply(client_name, enquiry_id, summary):
    id_line = f"Enquiry ID: #{enquiry_id}\n\n" if enquiry_id else ""
    return f"""Dear {client_name},

Thank you for contacting us.

We have received your enquiry regarding: {summary}

{id_line}Our team will reach back shortly to assist you.

Best regards,
Smart Enquiry Team
"""


def create_enquiry_from_email(from_email: str, from_name: str, subject: str, body: str,
                              source="Email", message_id=None, thread_key=None):
    from_email = (from_email or "").strip().lower()
    from_name = (from_name or "Customer").strip()
    subject = (subject or "").strip()
    body = (body or "").strip()

    full_text = f"Subject: {subject}\n\n{body}" if subject else body
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
        inbound_subject=subject,
        inbound_message_id=message_id,
        thread_key=thread_key,
    )
    db.session.add(enq)
    db.session.flush()
    db.session.add(ActivityLog(
        enquiry_id=enq.id,
        action=f"Enquiry auto-created from {source.lower()}. {'New client.' if is_new else 'Existing client.'} "
               f"Category: {enq.category}, Priority: {enq.priority}"
    ))
    reply_text = build_reply(client.name, enq.id, enq.ai_summary)
    enq.suggested_response = reply_text
    enq.reply_status = "pending_manual"
    db.session.commit()
    return enq, client, is_new, reply_text


@email_bp.route("/api/webhook/email", methods=["POST"])
def receive_email():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    from_email = (data.get("from_email") or "").strip().lower()
    from_name  = (data.get("from_name")  or "Customer").strip()
    subject    = (data.get("subject")    or "").strip()
    body       = (data.get("body")       or "").strip()
    message_id = (data.get("message_id") or "").strip()
    in_reply_to = (data.get("in_reply_to") or "").strip()
    references = (data.get("references") or "").strip()

    if not from_email or not body:
        return jsonify({"error": "from_email and body are required"}), 400

    is_new_thread, thread_key, existing_enquiry = check_and_register_thread(
        client_email=from_email,
        category="General",
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        subject=subject,
        body=body,
    )

    if is_new_thread or not existing_enquiry:
        enq, client, is_new, reply_text = create_enquiry_from_email(
            from_email, from_name, subject, body,
            source="Email", message_id=message_id, thread_key=thread_key
        )
        if message_id:
            db.session.add(EmailLog(
                sender=from_email,
                subject=subject,
                message_id=message_id,
                enquiry_id=enq.id
            ))
            db.session.commit()

        return jsonify({
            "success": True, "enquiry_id": enq.id, "client_id": client.id,
            "is_new_client": is_new, "is_new_thread": True,
            "category": enq.category, "priority": enq.priority,
            "reply_to": from_email, "reply_subject": f"Re: {subject} [Enquiry #{enq.id}]",
            "reply_body": reply_text,
            "auto_reply_sent": False
        }), 200
    else:
        # Existing thread - DO NOT create duplicate enquiry
        clean_body = re.sub(r"(?m)^[ \t]*>[^\r\n]*[\r\n]?", "", body or "")
        clean_body = re.sub(r"(?is)\nOn .*?wrote:\s*.*$", "", clean_body).strip() or body.strip()

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        existing_enquiry.description = (existing_enquiry.description or "").strip() + f"\n\n--- Customer Follow-up ({timestamp}) ---\n{clean_body}"
        existing_enquiry.updated_at = datetime.utcnow()
        if existing_enquiry.status in ("New", "Resolved", "Closed"):
            existing_enquiry.status = "In Discussion"

        followup_draft = generate_followup_draft(existing_enquiry, from_name, body)
        existing_enquiry.suggested_response = followup_draft
        existing_enquiry.reply_status = "pending_manual"

        db.session.add(ActivityLog(
            enquiry_id=existing_enquiry.id,
            action=f"Follow-up email received: '{clean_body[:80]}' — auto-reply skipped, draft queued for manual review"
        ))
        if message_id:
            db.session.add(EmailLog(
                sender=from_email,
                subject=subject,
                message_id=message_id,
                enquiry_id=existing_enquiry.id
            ))
        db.session.commit()

        return jsonify({
            "success": True, "enquiry_id": existing_enquiry.id, "client_id": existing_enquiry.client_id,
            "is_new_client": False, "is_new_thread": False, "is_followup": True,
            "category": existing_enquiry.category, "priority": existing_enquiry.priority,
            "reply_to": from_email, "reply_subject": f"Re: {subject} [Enquiry #{existing_enquiry.id}]",
            "reply_body": followup_draft,
            "auto_reply_sent": False
        }), 200


@email_bp.route("/api/email/check-inbox", methods=["POST", "GET"])
def check_inbox():
    missing = missing_mail_settings()
    if missing:
        return jsonify({
            "error": "Email intake is not configured.",
            "missing_env_vars": missing,
        }), 400

    try:
        emails = fetch_unread_emails(limit=10, mark_seen=True)
    except Exception as e:
        return jsonify({"error": f"Could not connect to mailbox: {e}"}), 502

    created = []
    for msg in emails:
        message_id = msg.get("message_id", "")
        if message_id:
            exists = Enquiry.query.filter_by(inbound_message_id=message_id).first()
            if not exists:
                exists = EmailLog.query.filter_by(message_id=message_id).first()
            if exists:
                continue

        is_new_thread, thread_key, existing_enquiry = check_and_register_thread(
            client_email=msg["sender_email"],
            category="General",
            message_id=message_id,
            in_reply_to=msg.get("in_reply_to", ""),
            references=msg.get("references", ""),
            subject=msg.get("subject", ""),
            body=msg.get("body", ""),
        )

        if is_new_thread or not existing_enquiry:
            enq, client, is_new, reply_text = create_enquiry_from_email(
                from_email=msg["sender_email"],
                from_name=msg["sender_name"],
                subject=msg["subject"],
                body=msg["body"],
                source="Email",
                message_id=message_id,
                thread_key=thread_key,
            )
            if message_id:
                db.session.add(EmailLog(
                    sender=msg["sender_email"],
                    subject=msg["subject"],
                    message_id=message_id,
                    enquiry_id=enq.id
                ))

            # Auto-reply ONLY to new threads
            send_result = send_reply(
                to_email=msg["sender_email"],
                subject=msg["subject"],
                body=reply_text,
                in_reply_to=message_id,
                references=msg.get("references", ""),
            )
            enq.reply_status = "auto_sent" if send_result.get("sent") else "send_failed"
            if send_result.get("sent") and send_result.get("message_id"):
                db.session.add(EmailLog(
                    sender="CRM",
                    subject=f"Re: {msg['subject']}",
                    message_id=send_result.get("message_id"),
                    enquiry_id=enq.id
                ))
            db.session.commit()

            created.append({
                "enquiry_id": enq.id,
                "from": msg["sender_email"],
                "subject": msg["subject"],
                "is_new_client": is_new,
                "is_new_thread": True,
                "reply_sent": send_result.get("sent", False),
                "reply_error": send_result.get("error"),
            })
        else:
            # Ongoing thread follow-up: DO NOT CREATE ENQUIRY!
            enq = existing_enquiry
            clean_body = re.sub(r"(?m)^[ \t]*>[^\r\n]*[\r\n]?", "", msg["body"] or "")
            clean_body = re.sub(r"(?is)\nOn .*?wrote:\s*.*$", "", clean_body).strip() or msg["body"].strip()

            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            enq.description = (enq.description or "").strip() + f"\n\n--- Customer Follow-up ({timestamp}) ---\n{clean_body}"
            enq.updated_at = datetime.utcnow()
            if enq.status in ("New", "Resolved", "Closed"):
                enq.status = "In Discussion"

            followup_draft = generate_followup_draft(enq, msg["sender_name"], msg["body"])
            enq.suggested_response = followup_draft
            enq.reply_status = "pending_manual"

            db.session.add(ActivityLog(
                enquiry_id=enq.id,
                action=f"Follow-up email received: '{clean_body[:80]}' — auto-reply skipped, draft queued for manual review"
            ))
            if message_id:
                db.session.add(EmailLog(
                    sender=msg["sender_email"],
                    subject=msg["subject"],
                    message_id=message_id,
                    enquiry_id=enq.id
                ))
            db.session.commit()

            created.append({
                "enquiry_id": enq.id,
                "from": msg["sender_email"],
                "subject": msg["subject"],
                "is_new_client": False,
                "is_new_thread": False,
                "is_followup": True,
                "reply_sent": False,
                "reply_error": "Follow-up queued for manual review",
            })

    return jsonify({
        "success": True,
        "checked": len(emails),
        "enquiries_created": len([c for c in created if c.get("is_new_thread")]),
        "details": created,
    }), 200