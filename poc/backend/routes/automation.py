from flask import Blueprint, jsonify, request
from database import db
from models import ActivityLog, Client, Enquiry
from services.ai_service import analyse, generate_response, classify_and_summarise
from services.email_service import fetch_unread_emails, send_reply
from services.thread_service import check_and_register_thread

automation_bp = Blueprint("automation", __name__)


def log(enquiry_id, action):
    db.session.add(ActivityLog(enquiry_id=enquiry_id, action=action))


def save_enquiry_from_email(mail, ai_result):
    """Helper function to save enquiry from email data"""
    description = f"Subject: {mail.get('subject', 'No Subject')}\n\n{mail.get('body', 'No content')}"
    
    # Handle both possible field names for email
    email_address = mail.get("from_email") or mail.get("sender_email", "unknown@example.com")
    customer_name = mail.get("from_name") or mail.get("sender_name", "Unknown Customer")

    client = Client.query.filter_by(email=email_address.lower()).first()
    if not client:
        client = Client(name=customer_name, email=email_address.lower())
        db.session.add(client)
        db.session.flush()
    
    # Use the AI result from classify_and_summarise
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
        automation_state="Imported",
        suggested_response=ai_result.get("suggested_reply", ""),
        reply_status="pending_manual"  # Default, will be updated
    )
    db.session.add(enquiry)
    db.session.flush()
    log(enquiry.id, "Imported from unread email and AI response drafted")
    return enquiry


@automation_bp.route("/api/automation/email/sync", methods=["POST"])
def sync_emails():
    """Sync unread emails and auto-reply to first-time contacts"""
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 10))
    mark_seen = bool(data.get("mark_seen", False))
    
    try:
        emails = fetch_unread_emails(limit=limit, mark_seen=mark_seen)
        print(f"📨 Fetched {len(emails)} emails")
    except Exception as e:
        print(f"❌ Error fetching emails: {e}")
        return jsonify({"error": str(e)}), 400
    
    results = []
    imported = []
    imported_count = 0
    skipped_count = 0

    for mail in emails:
        # Check if already exists
        message_id = mail.get("message_id", "")
        if message_id:
            exists = Enquiry.query.filter_by(inbound_message_id=message_id).first()
            if exists:
                skipped_count += 1
                continue
        
        # 1. Classify the email
        try:
            # Use the body for classification
            body = mail.get("body", "")
            ai_result = classify_and_summarise(body)
            print(f"✅ Classified email: {ai_result.get('category')}")
        except Exception as e:
            print(f"❌ AI classification error: {e}")
            # Fallback if AI service fails
            ai_result = {
                "category": "General",
                "priority": "Medium",
                "summary": "AI analysis failed",
                "suggested_reply": "Thank you for your email. Our team will review your query and get back to you shortly."
            }
        
        # 2. Save enquiry to DB
        enquiry = save_enquiry_from_email(mail, ai_result)

        # 3. Check thread: first contact for this client+issue?
        try:
            # Get email for thread check
            email_address = mail.get("from_email") or mail.get("sender_email", "unknown@example.com")
            is_first_contact = check_and_register_thread(
                client_email=email_address,
                category=ai_result.get("category", "General")
            )
            print(f"🔍 Thread check: {is_first_contact}")
        except Exception as e:
            # If thread service fails, default to manual review
            print(f"⚠️ Thread check error: {e}")
            is_first_contact = False
            log(enquiry.id, f"Thread check failed: {str(e)}")

        if is_first_contact:
            # AUTO-SEND
            try:
                draft = ai_result.get("suggested_reply", "")
                send_result = send_reply(
                    to_email=email_address,
                    subject=f"Re: {mail.get('subject', 'Your enquiry')}",
                    body=draft
                )
                enquiry.reply_status = "auto_sent" if send_result.get("sent") else "send_failed"
                log(
                    enquiry.id, 
                    f"Auto-reply sent" if send_result.get("sent") 
                    else f"Auto-reply failed: {send_result.get('error', 'Unknown error')}"
                )
            except Exception as e:
                print(f"❌ Send reply error: {e}")
                enquiry.reply_status = "send_failed"
                log(enquiry.id, f"Auto-reply failed: {str(e)}")
        else:
            # QUEUE FOR MANUAL REVIEW
            enquiry.reply_status = "pending_manual"
            log(enquiry.id, "Follow-up detected — queued for manual reply")

        db.session.commit()
        imported_count += 1
        imported.append(enquiry)

        results.append({
            "enquiry_id": enquiry.id,
            "client": email_address,
            "category": ai_result.get("category", "General"),
            "is_first_contact": is_first_contact,
            "reply_status": enquiry.reply_status
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