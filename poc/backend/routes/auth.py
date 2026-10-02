from flask import Blueprint, request, jsonify, g
from database import db
from models import User, Client
import hashlib, os, time, re, secrets
from services.email_service import send_login_otp
from functools import wraps

auth_bp = Blueprint("auth", __name__)
TOKENS = {}
LOGIN_OTPS = {}

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

    user = User(name=name, email=email, role=role)
    user.set_password(password)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    try:
        send_login_otp(email, otp)
    except RuntimeError as exc:
        return jsonify({"error": f"Could not send the verification email. No account was created. {exc}"}), 503
    challenge = secrets.token_urlsafe(32)
    LOGIN_OTPS[challenge] = {
        "pending_user": {
            "name": name, "email": email, "password_hash": user.password_hash,
            "phone": data.get("phone", ""), "company": data.get("company", ""),
        },
        "otp": otp, "expires_at": time.time() + 600, "attempts": 0,
    }
    return jsonify({"challenge": challenge, "message": "A verification code has been sent. Your account will be created after verification."}), 202


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "").strip().lower()
    if not EMAIL_REGEX.fullmatch(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if role not in ("client", "admin"):
        return jsonify({"error": "Choose Client or Admin to continue."}), 400
    user = User.query.filter_by(email=email).first()
    if not user or user.role != role or not user.check_password(data.get("password", "")):
        return jsonify({"error": "Invalid email or password"}), 401
    otp = f"{secrets.randbelow(1_000_000):06d}"
    try:
        send_login_otp(email, otp)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    challenge = secrets.token_urlsafe(32)
    LOGIN_OTPS[challenge] = {"user_id": user.id, "otp": otp, "expires_at": time.time() + 600, "attempts": 0}
    return jsonify({"challenge": challenge, "message": "A verification code has been sent to your email."}), 200


@auth_bp.route("/api/auth/verify-otp", methods=["POST"])
def verify_login_otp():
    data = request.get_json(silent=True) or {}
    challenge = data.get("challenge") or ""
    code = (data.get("otp") or "").strip()
    record = LOGIN_OTPS.get(challenge)
    if not record or record["expires_at"] < time.time():
        LOGIN_OTPS.pop(challenge, None)
        return jsonify({"error": "This verification code has expired. Please log in again."}), 401
    if record["attempts"] >= 5:
        LOGIN_OTPS.pop(challenge, None)
        return jsonify({"error": "Too many incorrect attempts. Please log in again."}), 429
    if not re.fullmatch(r"\d{6}", code) or not secrets.compare_digest(record["otp"], code):
        record["attempts"] += 1
        return jsonify({"error": "Incorrect verification code."}), 401
    LOGIN_OTPS.pop(challenge, None)
    pending_user = record.get("pending_user")
    if pending_user:
        if User.query.filter_by(email=pending_user["email"]).first():
            return jsonify({"error": "An account with this email is already registered. Please log in."}), 409
        client = Client.query.filter_by(email=pending_user["email"]).first()
        if not client:
            client = Client(
                name=pending_user["name"], email=pending_user["email"],
                phone=pending_user["phone"], company=pending_user["company"],
            )
            db.session.add(client)
            db.session.flush()
        user = User(
            name=pending_user["name"], email=pending_user["email"],
            role="client", client_id=client.id,
            password_hash=pending_user["password_hash"],
        )
        db.session.add(user)
        db.session.commit()
    else:
        user = User.query.get(record["user_id"])
    if not user:
        return jsonify({"error": "Account not found."}), 404
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
