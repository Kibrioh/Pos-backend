from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from extensions import db
from models import User
from utils.auth import get_current_user, login_required, manager_required
from utils.password_policy import password_policy_error

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

VALID_ROLES = ("manager", "cashier")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify(status="error",
                       message="Username and password are required"), 400

    user = User.query.filter(
        db.func.lower(User.username) == username.lower()
    ).first()

    # Same message for unknown user and wrong password (no user enumeration)
    if user is None or not user.check_password(password):
        return jsonify(status="error", message="Invalid username or password"), 401

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )
    return jsonify(status="success", access_token=token, user=user.to_dict()), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify(status="success", user=get_current_user().to_dict()), 200


@auth_bp.post("/register")
@manager_required
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "cashier")

    errors = {}
    if len(username) < 3:
        errors["username"] = "At least 3 characters"
    if not name:
        errors["name"] = "Name is required"
    password_error = password_policy_error(password)
    if password_error:
        errors["password"] = password_error
    if role not in VALID_ROLES:
        errors["role"] = f"Must be one of {VALID_ROLES}"
    if errors:
        return jsonify(status="error", message="Validation failed",
                       errors=errors), 400

    if User.query.filter(db.func.lower(User.username) == username.lower()).first():
        return jsonify(status="error", message="Username already exists"), 409

    user = User(username=username, name=name, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(status="success", user=user.to_dict()), 201


@auth_bp.post("/change-password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_pw = data.get("old_password") or ""
    new_pw = data.get("new_password") or ""
    user = get_current_user()

    if not user.check_password(old_pw):
        return jsonify(status="error",
                       message="Current password is incorrect"), 401
    password_error = password_policy_error(new_pw)
    if password_error:
        return jsonify(status="error",
                       message=password_error), 400

    user.set_password(new_pw)
    db.session.commit()
    return jsonify(status="success", message="Password updated"), 200

@auth_bp.get("/users")
@manager_required
def list_users():
    query = User.query
    role = (request.args.get("role") or "").strip().lower()
    if role:
        if role not in VALID_ROLES:
            return jsonify(status="error", message="Invalid user role filter"), 400
        query = query.filter(db.func.lower(User.role) == role)

    users = query.order_by(User.created_at.desc()).all()
    return jsonify(status="success", users=[u.to_dict() for u in users]), 200
