from flask import Blueprint, jsonify, request

from extensions import db
from models import Sale
from services.returns_service import create_return
from services.sales_service import create_sale
from services.stock_service import ServiceError
from services.shift_service import get_current_shift
from utils.auth import get_current_user, login_required, manager_required

bp = Blueprint("sales", __name__, url_prefix="/api/sales")


@bp.post("")
@login_required
def make_sale():
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    payment_method = str(payload.get("payment_method") or "cash").strip().lower()[:30]
    if payment_method not in {"cash", "card", "m-pesa"}:
        return jsonify(status="error", message="Payment method must be cash, card, or m-pesa"), 400

    shift_id = None
    if user.role == "cashier":
        shift = get_current_shift(user.id, lock=True)
        if shift is None:
            return jsonify(status="error", message="Open a cashier shift before completing a sale"), 409
        shift_id = shift.id

    try:
        sale = create_sale(
            user.id,
            payload.get("items"),
            payment_method,
            shift_id,
            payload.get("amount_tendered"),
        )
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


@bp.post("/<int:sale_id>/returns")
@manager_required
def return_sale(sale_id):
    payload = request.get_json(silent=True) or {}
    try:
        return_record = create_return(get_current_user(), sale_id, payload)
    except ServiceError as error:
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(return_record.to_dict()), 201
