from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models import Category

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("")
def get_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify([category.to_dict() for category in categories])


@bp.get("/<int:category_id>")
def get_category(category_id):
    category = Category.query.get_or_404(category_id)
    return jsonify(category.to_dict())


@bp.post("")
def create_category():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"error": "Category with this name already exists."}), 409

    category = Category(
        name=name,
        description=payload.get("description"),
    )
    db.session.add(category)
    db.session.commit()

    return jsonify(category.to_dict()), 201


@bp.put("/<int:category_id>")
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    payload = request.get_json(silent=True) or {}

    new_name = (payload.get("name") or "").strip()
    if new_name:
        if Category.query.filter(Category.id != category_id, Category.name == new_name).first():
            return jsonify({"error": "Category with this name already exists."}), 409
        category.name = new_name

    if "description" in payload:
        category.description = payload.get("description")

    if "is_active" in payload:
        category.is_active = bool(payload.get("is_active"))

    db.session.commit()
    return jsonify(category.to_dict())
