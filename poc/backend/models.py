from database import db
from datetime import datetime
import hashlib
import os


class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role          = db.Column(db.String(20), default="client")
    client_id     = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        salt = os.urandom(16).hex()
        hashed = hashlib.sha256((salt + password).encode()).hexdigest()
        self.password_hash = f"{salt}:{hashed}"

    def check_password(self, password):
        salt, hashed = self.password_hash.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "email": self.email,
            "role": self.role, "client_id": self.client_id,
        }


class Client(db.Model):
    __tablename__ = "clients"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(100), unique=True, nullable=False)
    phone      = db.Column(db.String(20))
    company    = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "email": self.email,
            "phone": self.phone or "", "company": self.company or "",
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }


class Enquiry(db.Model):
    __tablename__ = "enquiries"

    id             = db.Column(db.Integer, primary_key=True)
    client_id      = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    customer_name  = db.Column(db.String(100), nullable=False)
    phone          = db.Column(db.String(20))
    email          = db.Column(db.String(100))
    source         = db.Column(db.String(50))
    description    = db.Column(db.Text, nullable=False)
    category       = db.Column(db.String(50))
    priority       = db.Column(db.String(20))
    ai_summary     = db.Column(db.Text)
    status         = db.Column(db.String(50), default="New")
    follow_up_date = db.Column(db.String(20))
    notes          = db.Column(db.Text, default="")
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    logs = db.relationship("ActivityLog", backref="enquiry", lazy=True,
                           cascade="all, delete-orphan",
                           order_by="ActivityLog.created_at")

    def to_dict(self, include_logs=True):
        d = {
            "id": self.id, "client_id": self.client_id,
            "customer_name": self.customer_name,
            "phone": self.phone or "", "email": self.email or "",
            "source": self.source or "", "description": self.description,
            "category": self.category or "General",
            "priority": self.priority or "Medium",
            "ai_summary": self.ai_summary or "",
            "status": self.status,
            "follow_up_date": self.follow_up_date or "",
            "notes": self.notes or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else "",
        }
        if include_logs:
            d["logs"] = [l.to_dict() for l in self.logs]
        return d


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id         = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey("enquiries.id"), nullable=False)
    action     = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "enquiry_id": self.enquiry_id,
            "action": self.action,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
        }


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id         = db.Column(db.Integer, primary_key=True)
    client_id  = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages   = db.relationship("ChatMessage", backref="session", lazy=True,
                                 order_by="ChatMessage.created_at")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    sender     = db.Column(db.String(10))
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
