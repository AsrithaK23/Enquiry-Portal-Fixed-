from flask import Blueprint, request, jsonify
from database import db
from models import Enquiry, ActivityLog
from services.ai_service import analyse
from datetime import datetime

enquiries_bp = Blueprint("enquiries", __name__)


def log(enquiry_id, action):
    db.session.add(ActivityLog(enquiry_id=enquiry_id, action=action))


@enquiries_bp.route("/api/enquiries", methods=["POST"])
def create_enquiry():
    data = request.get_json()
    if not data.get("customer_name") or not data.get("description"):
        return jsonify({"error": "customer_name and description are required"}), 400

    ai = analyse(data["description"])

    enq = Enquiry(
        customer_name = data["customer_name"].strip(),
        phone         = data.get("phone", ""),
        email         = data.get("email", ""),
        source        = data.get("source", ""),
        description   = data["description"].strip(),
        category      = ai["category"],
        priority      = ai["priority"],
        ai_summary    = ai["ai_summary"],
        status        = "New",
        follow_up_date= data.get("follow_up_date", ""),
        notes         = data.get("notes", ""),
    )
    db.session.add(enq)
    db.session.flush()
    log(enq.id, f"Enquiry created. Category: {enq.category}, Priority: {enq.priority}")
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
        query = query.filter(
            db.or_(
                Enquiry.customer_name.ilike(f"%{search}%"),
                Enquiry.email.ilike(f"%{search}%"),
            )
        )

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
        if data["follow_up_date"] != enq.follow_up_date:
            changes.append(f"Follow-up date set to {data['follow_up_date']}")
        enq.follow_up_date = data["follow_up_date"]

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
