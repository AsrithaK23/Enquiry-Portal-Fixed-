from flask import Blueprint, jsonify, request
from database import db
from models import ActivityLog, Client, Enquiry, EmailLog
from datetime import datetime
import re
from services.ai_service import analyse, generate_response, classify_and_summarise, generate_followup_draft
from services.email_service import fetch_unread_emails, send_reply
from services.thread_service import check_and_register_thread

automation_bp = Blueprint("automation", __name__)


def log(enquiry_id, action):
    db.session.add(ActivityLog(enquiry_id=enquiry_id, action=action))


def save_enquiry_from_email(mail, ai_result, thread_key=None, draft_response=""):
    """Helper function to save enquiry from email data"""
    description = f"Subject: {mail.get('subject', 'No Subject')}\n\n{mail.get('body', 'No content')}"
    
    # Handle both possible field names for email
    email_address = mail.get("from_email") or mail.get("sender_email", "unknown@example.com")
    customer_name = mail.get("from_name") or mail.get("sender_name", "Customer")

    client = Client.query.filter_by(email=email_address.lower()).first()
    if not client:
        client = Client(name=customer_name, email=email_address.lower())
        db.session.add(client)
        db.session.flush()
    
    enquiry = Enquiry(
        client_id=client.id,
        customer_name=customer_name,
        email=email_address,
        source="Email",
        description=description,
        category=ai_result.get("category", "General"),
        priority=ai_result.get("priority", "Medium"),
        ai_summary=ai_result.get("summary", ""),
        status="New",
        inbound_subject=mail.get("subject", ""),
        inbound_message_id=mail.get("message_id") or None,
        thread_key=thread_key,
        automation_state="Imported",
        suggested_response=draft_response or ai_result.get("suggested_reply", ""),
        reply_status="pending_manual"
    )
    db.session.add(enquiry)
    db.session.flush()
    log(enquiry.id, "Imported from unread email and AI response drafted")
    return enquiry


@automation_bp.route("/api/automation/email/sync", methods=["POST"])
def sync_emails():
    """Sync unread emails and auto-reply ONLY to new threads"""
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 10))
    mark_seen = bool(data.get("mark_seen", False))
    
    try:
        emails = fetch_unread_emails(limit=limit, mark_seen=mark_seen)
        print(f"Fetched {len(emails)} emails")
    except Exception as e:
        print(f"Error fetching emails: {e}")
        return jsonify({"error": str(e)}), 400
    
    results = []
    imported = []
    imported_count = 0
    skipped_count = 0

    for mail in emails:
        message_id = mail.get("message_id", "")
        if message_id:
            exists = Enquiry.query.filter_by(inbound_message_id=message_id).first()
            if not exists:
                exists = EmailLog.query.filter_by(message_id=message_id).first()
            if exists:
                skipped_count += 1
                continue

        email_address = mail.get("from_email") or mail.get("sender_email", "unknown@example.com")
        customer_name = mail.get("from_name") or mail.get("sender_name", "Customer")
        subject = mail.get("subject", "")
        body = mail.get("body", "")
        full_text = f"Subject: {subject}\n\n{body}" if subject else body

        # 1. Thread check (multi-signal: RFC headers, normalized subject, enquiry IDs)
        is_first_contact, thread_key, existing_enquiry = check_and_register_thread(
            client_email=email_address,
            category="General",
            message_id=message_id,
            in_reply_to=mail.get("in_reply_to", ""),
            references=mail.get("references", ""),
            subject=subject,
            body=body,
        )

        # 2. Handle draft and auto-reply depending on thread status
        if is_first_contact or not existing_enquiry:
            # NEW THREAD: Classify, save enquiry, send auto-reply
            try:
                ai_result = classify_and_summarise(full_text, customer_name=customer_name)
            except Exception as e:
                print(f"AI classification error: {e}")
                ai_result = {
                    "category": "General",
                    "priority": "Medium",
                    "summary": "Customer sent an enquiry requiring review.",
                    "suggested_reply": f"Dear {customer_name},\n\nThank you for contacting us. We have received your enquiry regarding: Customer sent an enquiry requiring review.\n\nOur team will reach back shortly to assist you.\n\nBest regards,\nSmart Enquiry Team"
                }

            draft_text = ai_result.get("suggested_reply", "")
            enquiry = save_enquiry_from_email(mail, ai_result, thread_key, draft_response=draft_text)

            if message_id:
                db.session.add(EmailLog(
                    sender=email_address,
                    subject=subject,
                    message_id=message_id,
                    enquiry_id=enquiry.id
                ))

            try:
                send_result = send_reply(
                    to_email=email_address,
                    subject=subject,
                    body=draft_text,
                    in_reply_to=message_id,
                    references=mail.get("references", ""),
                )
                enquiry.reply_status = "auto_sent" if send_result.get("sent") else "send_failed"
                log(
                    enquiry.id,
                    "Auto-reply sent for new enquiry thread" if send_result.get("sent")
                    else f"Auto-reply failed: {send_result.get('error', 'Unknown error')}"
                )
                if send_result.get("sent") and send_result.get("message_id"):
                    db.session.add(EmailLog(
                        sender="CRM",
                        subject=f"Re: {subject}",
                        message_id=send_result.get("message_id"),
                        enquiry_id=enquiry.id
                    ))
            except Exception as e:
                print(f"Send reply error: {e}")
                enquiry.reply_status = "send_failed"
                log(enquiry.id, f"Auto-reply failed: {str(e)}")

            db.session.commit()
            imported_count += 1
            imported.append(enquiry)

            results.append({
                "enquiry_id": enquiry.id,
                "client": email_address,
                "category": ai_result.get("category", "General"),
                "is_first_contact": True,
                "reply_status": enquiry.reply_status
            })
        else:
            # ONGOING THREAD: DO NOT CREATE A NEW ENQUIRY! DO NOT AUTO-REPLY.
            # Attach follow-up to existing_enquiry.
            enquiry = existing_enquiry

            clean_body = re.sub(r"(?m)^[ \t]*>[^\r\n]*[\r\n]?", "", body or "")
            clean_body = re.sub(r"(?is)\nOn .*?wrote:\s*.*$", "", clean_body).strip() or body.strip()

            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            followup_note = f"\n\n--- Customer Follow-up ({timestamp}) ---\n{clean_body}"
            enquiry.description = (enquiry.description or "").strip() + followup_note
            enquiry.updated_at = datetime.utcnow()
            if enquiry.status in ("New", "Resolved", "Closed"):
                enquiry.status = "In Discussion"

            # Draft response for employee manual review
            followup_draft = generate_followup_draft(
                enquiry=enquiry,
                customer_name=customer_name,
                message_body=body
            )
            enquiry.suggested_response = followup_draft
            enquiry.reply_status = "pending_manual"

            log(enquiry.id, f"Follow-up email received: '{clean_body[:80]}' — auto-reply skipped, draft saved for manual review")

            if message_id:
                db.session.add(EmailLog(
                    sender=email_address,
                    subject=subject,
                    message_id=message_id,
                    enquiry_id=enquiry.id
                ))

            db.session.commit()
            imported_count += 1
            imported.append(enquiry)

            results.append({
                "enquiry_id": enquiry.id,
                "client": email_address,
                "category": enquiry.category,
                "is_first_contact": False,
                "is_followup": True,
                "reply_status": "pending_manual"
            })

    return jsonify({
        "synced": imported_count,
        "skipped": skipped_count,
        "imported": [e.to_dict(include_logs=False) for e in imported],
        "results": results
    }), 200


# ─── Test endpoint ──────────────────────────────
@automation_bp.route("/api/automation/test", methods=["GET"])
def test_route():
    return jsonify({"message": "Automation route is working!", "status": "ok"}), 200


@automation_bp.route("/api/automation/enquiries/<int:id>/reply", methods=["PUT", "POST"])
def manual_reply(id):
    """Save an edited draft or send it manually after employee review."""
    enquiry = Enquiry.query.get_or_404(id)
    data = request.get_json(silent=True) or {}
    draft = (data.get("body") or enquiry.suggested_response or "").strip()
    if not draft:
        return jsonify({"error": "Reply body is required"}), 400

    enquiry.suggested_response = draft
    if request.method == "PUT" or not data.get("send"):
        db.session.commit()
        return jsonify(enquiry.to_dict(include_logs=False)), 200

    if not enquiry.email:
        return jsonify({"error": "This enquiry has no customer email address"}), 400

    result = send_reply(
        to_email=enquiry.email,
        subject=enquiry.inbound_subject or "Your enquiry",
        body=draft,
        in_reply_to=enquiry.inbound_message_id,
        references=enquiry.thread_key,
    )
    enquiry.reply_status = "auto_sent" if result.get("sent") else "send_failed"
    log(enquiry.id, "Manual reply sent" if result.get("sent") else f"Manual reply failed: {result.get('error', 'Unknown')}")
    if result.get("sent") and result.get("message_id"):
        db.session.add(EmailLog(
            sender="CRM",
            subject=enquiry.inbound_subject or "Your enquiry",
            message_id=result.get("message_id"),
            enquiry_id=enquiry.id
        ))
    db.session.commit()
    if not result.get("sent"):
        return jsonify({"error": result.get("error", "Unable to send reply")}), 502
    return jsonify(enquiry.to_dict(include_logs=False)), 200


# Keep the old endpoint for backward compatibility if needed
@automation_bp.route("/api/automation/email/sync-old", methods=["POST"])
def sync_email_old():
    """Original email sync endpoint (kept for backward compatibility)"""
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 10))
    mark_seen = bool(data.get("mark_seen", False))

    try:
        messages = fetch_unread_emails(limit=limit, mark_seen=mark_seen)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    imported = []
    skipped = 0

    for message in messages:
        message_id = message.get("message_id") or None
        if message_id:
            exists = Enquiry.query.filter_by(inbound_message_id=message_id).first()
            if exists:
                skipped += 1
                continue

        description = f"Subject: {message.get('subject', '')}\n\n{message.get('body', '')}"
        ai = analyse(description)
        enquiry = Enquiry(
            customer_name=message.get("sender_name", "Unknown"),
            email=message.get("sender_email", "unknown@example.com"),
            source="Email",
            description=description,
            category=ai["category"],
            priority=ai["priority"],
            ai_summary=ai["ai_summary"],
            status="New",
            inbound_subject=message.get("subject", ""),
            inbound_message_id=message_id,
            automation_state="Imported",
            reply_status="pending_manual"
        )
        enquiry.suggested_response = generate_response(enquiry)
        db.session.add(enquiry)
        db.session.flush()
        log(enquiry.id, "Imported from unread email and AI response drafted")
        imported.append(enquiry)

    db.session.commit()
    return jsonify({
        "imported_count": len(imported),
        "skipped_count": skipped,
        "imported": [e.to_dict(include_logs=False) for e in imported],
    }), 201