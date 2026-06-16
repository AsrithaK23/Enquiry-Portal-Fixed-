from flask import Blueprint, request, jsonify
from database import db
from models import Client, Enquiry, ActivityLog
from services.ai_service import analyse

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


@email_bp.route("/api/webhook/email", methods=["POST"])
def receive_email():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    from_email = (data.get("from_email") or "").strip().lower()
    from_name  = (data.get("from_name")  or "Unknown Sender").strip()
    subject    = (data.get("subject")    or "").strip()
    body       = (data.get("body")       or "").strip()

    if not from_email or not body:
        return jsonify({"error": "from_email and body are required"}), 400

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
        source="Email", description=body,
        category=ai["category"], priority=ai["priority"],
        ai_summary=ai["ai_summary"], status="New",
    )
    db.session.add(enq)
    db.session.flush()
    db.session.add(ActivityLog(
        enquiry_id=enq.id,
        action=f"Enquiry auto-created from email. {'New client.' if is_new else 'Existing client.'} "
               f"Category: {enq.category}, Priority: {enq.priority}"
    ))
    db.session.commit()

    reply_text = build_reply(client.name, enq.id, enq.category, enq.priority)

    return jsonify({
        "success": True, "enquiry_id": enq.id, "client_id": client.id,
        "is_new_client": is_new, "category": enq.category, "priority": enq.priority,
        "reply_to": from_email, "reply_subject": f"Re: {subject} [Enquiry #{enq.id}]",
        "reply_body": reply_text,
    }), 200
