from flask import Blueprint, jsonify, request
from extensions import db

from services.purchasing_service import (
    create_purchase_order,
    create_supplier,
    list_purchase_orders,
    list_suppliers,
    receive_purchase_order,
)
from services.stock_service import ServiceError
from utils.auth import get_current_user, manager_required

suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/api/suppliers")
purchase_orders_bp = Blueprint("purchase_orders", __name__, url_prefix="/api/purchase-orders")


@suppliers_bp.get("")
@manager_required
def get_suppliers():
    return jsonify([supplier.to_dict() for supplier in list_suppliers()]), 200


@suppliers_bp.post("")
@manager_required
def add_supplier():
    payload = request.get_json(silent=True) or {}
    try:
        supplier = create_supplier(get_current_user(), payload)
    except ServiceError as error:
        db.session.rollback()
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(supplier.to_dict()), 201


@purchase_orders_bp.get("")
@manager_required
def get_purchase_orders():
    return jsonify([order.to_dict() for order in list_purchase_orders()]), 200


@purchase_orders_bp.post("")
@manager_required
def add_purchase_order():
    payload = request.get_json(silent=True) or {}
    try:
        order = create_purchase_order(get_current_user(), payload)
    except ServiceError as error:
        db.session.rollback()
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(order.to_dict()), 201


@purchase_orders_bp.post("/<int:order_id>/receive")
@manager_required
def receive_order(order_id):
    payload = request.get_json(silent=True) or {}
    try:
        order = receive_purchase_order(get_current_user(), order_id, payload)
    except ServiceError as error:
        db.session.rollback()
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(order.to_dict()), 200
