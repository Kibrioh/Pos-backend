from flask import Blueprint, jsonify, request

from extensions import db
from models import Sale
from services.sales_service import create_sale
from services.stock_service import ServiceError
from utils.auth import get_current_user, login_required, manager_required

bp = Blueprint("sales", __name__, url_prefix="/api/sales")


@bp.post("")
@login_required
def make_sale():
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    payment_method = str(payload.get("payment_method") or "cash").strip().lower()[:30]

    try:
        sale = create_sale(user.id, payload.get("items"), payment_method)
    except ServiceError as err:
        return jsonify(status="error", message=str(err)), err.status_code

    return jsonify(sale.to_dict()), 201


@bp.get("")
@manager_required
def list_sales():
    sales = Sale.query.order_by(Sale.created_at.desc()).all()
    return jsonify([sale.to_dict() for sale in sales])


@bp.get("/mine")
@login_required
def my_sales():
    user = get_current_user()
    sales = (
        Sale.query.filter_by(user_id=user.id)
        .order_by(Sale.created_at.desc())
        .all()
    )
    return jsonify([sale.to_dict() for sale in sales])


@bp.get("/<int:sale_id>")
@login_required
def get_sale(sale_id):
    sale = db.session.get(Sale, sale_id)
    if sale is None:
        return jsonify(status="error", message="Sale not found"), 404
    return jsonify(sale.to_dict())
