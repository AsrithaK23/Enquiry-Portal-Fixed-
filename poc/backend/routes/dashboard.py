from flask import Blueprint, jsonify
from database import db
from models import Enquiry
from datetime import date
from models import Enquiry, EmailLog 

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard", methods=["GET"])
def dashboard():
    total   = Enquiry.query.count()
    new     = Enquiry.query.filter_by(status="New").count()
    in_disc = Enquiry.query.filter_by(status="In Discussion").count()
    quoted  = Enquiry.query.filter_by(status="Quoted").count()
    closed  = Enquiry.query.filter_by(status="Closed").count()
    dropped = Enquiry.query.filter_by(status="Dropped").count()

    today_str = date.today().isoformat()
    pending_followup = Enquiry.query.filter(
        Enquiry.follow_up_date != "",
        Enquiry.follow_up_date <= today_str,
        Enquiry.status.notin_(["Closed", "Dropped"])
    ).count()

    by_category = db.session.query(Enquiry.category, db.func.count(Enquiry.id)).group_by(Enquiry.category).all()
    by_priority = db.session.query(Enquiry.priority, db.func.count(Enquiry.id)).group_by(Enquiry.priority).all()

    recent = Enquiry.query.order_by(Enquiry.created_at.desc()).limit(5).all()
    try:
        from models import EmailLog
        emails_synced = EmailLog.query.count()
        emails_today  = EmailLog.query.filter(
            db.func.date(EmailLog.created_at) == date.today().isoformat()
        ).count()
    except Exception:
        emails_synced = 0
        emails_today  = 0

    return jsonify({
        "total": total, "new": new, "in_discussion": in_disc,
        "quoted": quoted, "closed": closed, "dropped": dropped,
        "pending_followup": pending_followup,
        "emails_synced": emails_synced,
        "emails_today": emails_today,
        "by_category": {k: v for k, v in by_category},
        "by_priority": {k: v for k, v in by_priority},
        "recent": [e.to_dict(include_logs=False) for e in recent],
    }), 200
