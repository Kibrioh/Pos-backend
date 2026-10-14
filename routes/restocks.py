from flask import Blueprint, jsonify, request

from services.stock_service import (
    ServiceError,
    delete_restock,
    get_restock_by_id,
    list_restocks,
    restock_product,
    update_restock,
)

bp = Blueprint("restocks", __name__, url_prefix="/api/restocks")


@bp.get("")
def all_restocks():
    return jsonify(list_restocks()), 200


@bp.get("/<int:restock_id>")
def get_restock(restock_id):
    try:
        return jsonify(get_restock_by_id(restock_id)), 200
    except ServiceError as e:
        return jsonify({"status": "error", "message": str(e)}), e.status_code


@bp.post("")
def create_restock():
    payload = request.get_json(silent=True) or {}
    try:
        result = restock_product(payload)
    except ServiceError as e:
        return jsonify({"status": "error", "message": str(e)}), e.status_code
    return jsonify(result), 201


@bp.put("/<int:restock_id>")
def update_restock_route(restock_id):
    payload = request.get_json(silent=True) or {}
    try:
        result = update_restock(restock_id, payload)
    except ServiceError as e:
        return jsonify({"status": "error", "message": str(e)}), e.status_code
    return jsonify(result), 200


@bp.delete("/<int:restock_id>")
def delete_restock_route(restock_id):
    try:
        result = delete_restock(restock_id)
    except ServiceError as e:
        return jsonify({"status": "error", "message": str(e)}), e.status_code
    return jsonify(result), 200
