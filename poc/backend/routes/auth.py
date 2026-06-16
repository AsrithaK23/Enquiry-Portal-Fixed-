from flask import Blueprint, request, jsonify, g
from database import db
from models import User, Client
import hashlib, os, time
from functools import wraps

auth_bp = Blueprint("auth", __name__)
TOKENS = {}


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
    data = request.get_json()
    if not data.get("email") or not data.get("password") or not data.get("name"):
        return jsonify({"error": "name, email and password required"}), 400
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 400

    role = data.get("role", "client")
    client_id = None
    if role == "client":
        client = Client.query.filter_by(email=data["email"]).first()
        if not client:
            client = Client(
                name=data["name"], email=data["email"],
                phone=data.get("phone", ""), company=data.get("company", ""),
            )
            db.session.add(client)
            db.session.flush()
        client_id = client.id

    user = User(name=data["name"], email=data["email"], role=role, client_id=client_id)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get("email")).first()
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
