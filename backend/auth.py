import hmac
import hashlib
import time
import base64
import json
from functools import wraps
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import Session
from .config import Config
from .models import User

TOKEN_EXPIRATION_SECONDS = 86400 * 7  # 7 days

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return check_password_hash(hashed, password)

def generate_token(user: User) -> str:
    """Generates simple signed HMAC token containing user ID, role, and expiration."""
    payload = {
        "uid": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "team_id": user.team_id,
        "exp": int(time.time()) + TOKEN_EXPIRATION_SECONDS
    }
    json_bytes = json.dumps(payload).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(json_bytes).decode("utf-8")
    signature = hmac.new(
        Config.SECRET_KEY.encode("utf-8"),
        b64_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{b64_payload}.{signature}"

def verify_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, signature = parts
        expected_sig = hmac.new(
            Config.SECRET_KEY.encode("utf-8"),
            b64_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        elif request.headers.get("X-Auth-Token"):
            token = request.headers.get("X-Auth-Token")

        # Allow fallback header role for quick API testing if no token provided
        role_header = request.headers.get("X-User-Role")

        if token:
            payload = verify_token(token)
            if not payload:
                return jsonify({"error": "Invalid or expired authorization token"}), 401
            g.current_user = payload
        elif role_header:
            g.current_user = {
                "uid": 1,
                "role": role_header.upper(),
                "name": f"Demo {role_header.capitalize()}",
                "email": f"{role_header.lower()}@helpdeskx.com"
            }
        else:
            return jsonify({"error": "Authentication required. Provide Bearer token or credentials."}), 401

        return f(*args, **kwargs)
    return decorated_function

def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            user_role = g.current_user.get("role", "").upper()
            allowed = [r.upper() for r in allowed_roles]
            if user_role not in allowed and "ADMIN" not in allowed:
                return jsonify({
                    "error": f"Access denied. Requires one of roles: {list(allowed_roles)}. Current role: {user_role}"
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

