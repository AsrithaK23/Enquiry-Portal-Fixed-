import re
from flask import Blueprint, request, jsonify
from database import db
from models import Client, Enquiry, ActivityLog
from services.ai_service import analyse, validate_enquiry_legitimacy
from datetime import datetime

enquiries_bp = Blueprint("enquiries", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_DIGITS_RE = re.compile(r"^\d{10}$")


def log(enquiry_id, action):
    db.session.add(ActivityLog(enquiry_id=enquiry_id, action=action))


@enquiries_bp.route("/api/enquiries", methods=["POST"])
def create_enquiry():
    data = request.get_json(silent=True) or {}
    customer_name = (data.get("customer_name") or "").strip()
    description   = (data.get("description") or "").strip()
    email         = (data.get("email") or "").strip().lower()
    raw_phone     = (data.get("phone") or "").strip()

    # 1. Required Client Name
    if not customer_name:
        return jsonify({"error": "Client Name is required."}), 400

    # 2. Compulsory & Valid Email
    if not email:
        return jsonify({"error": "Email is compulsory and required."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address (e.g. name@example.com or user@domain.in)."}), 400

    # 3. Phone validation (only digits, 10-15 digits if provided)
    clean_phone = re.sub(r"[\s\-+]", "", raw_phone)
    if clean_phone:
        if not clean_phone.isdigit() or not PHONE_DIGITS_RE.match(clean_phone):
            return jsonify({"error": "Phone number must contain exactly 10 digits only, without letters or symbols."}), 400

    # 4. Description & Gibberish / Lorem Ipsum Validation
    if not description:
        return jsonify({"error": "Description is required."}), 400

    is_legit, reason = validate_enquiry_legitimacy(description)
    if not is_legit:
        rej_msg = reason or "Placeholder text or gibberish is not accepted."
        return jsonify({"error": f"Please provide a legitimate enquiry description ({rej_msg})."}), 400

    ai = analyse(description)
    if not ai.get("is_legitimate", True):
        rej_msg = ai.get("rejection_reason") or "Placeholder text or gibberish is not accepted."
        return jsonify({"error": f"Please provide a legitimate enquiry description ({rej_msg})."}), 400

    # 5. Follow-up date validation (no past date allowed)
    raw_follow_up = (data.get("follow_up_date") or "").strip()
    if raw_follow_up:
        try:
            f_date = datetime.strptime(raw_follow_up, "%Y-%m-%d").date()
            if f_date < datetime.now().date():
                return jsonify({"error": "Follow-up date cannot be in the past. Please select today or a future date."}), 400
        except ValueError:
            return jsonify({"error": "Invalid follow-up date format (expected YYYY-MM-DD)."}), 400

    # 6. Client List Sync (creates or updates Client in the database)
    client = Client.query.filter_by(email=email).first()
    if not client:
        client = Client(
            name=customer_name,
            email=email,
            phone=clean_phone,
            company=data.get("company", ""),
        )
        db.session.add(client)
        db.session.flush()
    else:
        if clean_phone and not client.phone:
            client.phone = clean_phone
        if customer_name and (not client.name or client.name == "Customer"):
            client.name = customer_name

    enq = Enquiry(
        client_id     = client.id,
        customer_name = customer_name,
        phone         = clean_phone,
        email         = email,
        source        = data.get("source", "Manual"),
        description   = description,
        category      = ai["category"],
        priority      = ai["priority"],
        ai_summary    = ai["ai_summary"],
        status        = "New",
        follow_up_date= data.get("follow_up_date", ""),
        notes         = data.get("notes", ""),
    )
    db.session.add(enq)
    db.session.flush()
    log(enq.id, f"Enquiry created manually. Category: {enq.category}, Priority: {enq.priority}")
    db.session.commit()
    return jsonify(enq.to_dict()), 201


@enquiries_bp.route("/api/enquiries", methods=["GET"])
def get_enquiries():
    search   = request.args.get("search", "").strip().lower()
    status   = request.args.get("status", "")
    category = request.args.get("category", "")

    query = Enquiry.query
    if status:   query = query.filter(Enquiry.status == status)
    if category: query = query.filter(Enquiry.category == category)
    if search:
        search_num = search.lstrip("#").strip()
        conditions = [
            Enquiry.customer_name.ilike(f"%{search}%"),
            Enquiry.email.ilike(f"%{search}%"),
        ]
        if search_num.isdigit():
            conditions.append(Enquiry.id == int(search_num))
        query = query.filter(db.or_(*conditions))

    enquiries = query.order_by(Enquiry.created_at.desc()).all()
    return jsonify([e.to_dict(include_logs=False) for e in enquiries]), 200


@enquiries_bp.route("/api/enquiries/<int:id>", methods=["GET"])
def get_enquiry(id):
    enq = Enquiry.query.get_or_404(id)
    return jsonify(enq.to_dict()), 200


@enquiries_bp.route("/api/enquiries/<int:id>", methods=["PUT"])
def update_enquiry(id):
    enq  = Enquiry.query.get_or_404(id)
    data = request.get_json()
    changes = []

    if "status" in data and data["status"] != enq.status:
        changes.append(f"Status changed: {enq.status} → {data['status']}")
        enq.status = data["status"]

    if "notes" in data:
        if data["notes"] != enq.notes:
            changes.append("Notes updated")
        enq.notes = data["notes"]

    if "follow_up_date" in data:
        raw_follow_up = (data.get("follow_up_date") or "").strip()
        if raw_follow_up:
            try:
                f_date = datetime.strptime(raw_follow_up, "%Y-%m-%d").date()
                if f_date < datetime.now().date():
                    return jsonify({"error": "Follow-up date cannot be in the past. Please select today or a future date."}), 400
            except ValueError:
                return jsonify({"error": "Invalid follow-up date format (expected YYYY-MM-DD)."}), 400
        if raw_follow_up != enq.follow_up_date:
            changes.append(f"Follow-up date set to {raw_follow_up}")
        enq.follow_up_date = raw_follow_up

    if "category" in data: enq.category = data["category"]
    if "priority" in data: enq.priority = data["priority"]

    enq.updated_at = datetime.utcnow()
    for c in changes:
        log(enq.id, c)

    db.session.commit()
    return jsonify(enq.to_dict()), 200


@enquiries_bp.route("/api/enquiries/<int:id>", methods=["DELETE"])
def delete_enquiry(id):
    enq = Enquiry.query.get_or_404(id)
    db.session.delete(enq)
    db.session.commit()
    return jsonify({"message": f"Enquiry {id} deleted"}), 200


@enquiries_bp.route("/api/enquiries/<int:id>/summarise", methods=["POST"])
def summarise(id):
    enq = Enquiry.query.get_or_404(id)
    result = analyse(enq.description)
    enq.ai_summary = result["ai_summary"]
    log(enq.id, "AI summary regenerated")
    db.session.commit()
    return jsonify({"ai_summary": enq.ai_summary}), 200


@enquiries_bp.route("/api/classify", methods=["POST"])
def classify():
    text = (request.get_json() or {}).get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400
    return jsonify(analyse(text)), 200
