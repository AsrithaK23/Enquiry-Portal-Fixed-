from flask import Blueprint, request, jsonify, g
from database import db
from models import User, Client
import hashlib, os, time, re
from functools import wraps

auth_bp = Blueprint("auth", __name__)
TOKENS = {}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$")


def validate_password_strength(password: str) -> tuple[bool, str]:
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number (0-9)."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must contain at least one special character (e.g. !@#$%^&*)."
    return True, ""


def generate_token(user_id):
    raw = f"{user_id}{time.time()}{os.urandom(8).hex()}"
    token = hashlib.sha256(raw.encode()).hexdigest()
    TOKENS[token] = user_id
    return token


def get_user_from_token(token):
    user_id = TOKENS.get(token)
    return User.query.get(user_id) if user_id else None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        user = get_user_from_token(token)
        if not user:
            return jsonify({"error": "Unauthorised"}), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    raw_email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not name or not raw_email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400

    email = raw_email.lower()
    if not EMAIL_REGEX.match(email):
        return jsonify({"error": "Please enter a valid email address (e.g. name@example.com or user@domain.in)."}), 400

    valid_pwd, pwd_error = validate_password_strength(password)
    if not valid_pwd:
        return jsonify({"error": pwd_error}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email is already registered."}), 400

    # Public sign-up is strictly restricted to 'client' role to prevent privilege escalation
    role = "client"

    client = Client.query.filter_by(email=email).first()
    if not client:
        client = Client(
            name=name, email=email,
            phone=data.get("phone", ""), company=data.get("company", ""),
        )
        db.session.add(client)
        db.session.flush()
    client_id = client.id

    user = User(name=name, email=email, role=role, client_id=client_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(data.get("password", "")):
        return jsonify({"error": "Invalid email or password"}), 401
    token = generate_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 200


@auth_bp.route("/api/auth/me", methods=["GET"])
@require_auth
def me():
    return jsonify(g.user.to_dict()), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
@require_auth
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    TOKENS.pop(token, None)
    return jsonify({"message": "Logged out"}), 200