from flask import Blueprint, jsonify, request

from services.shift_service import (
    close_shift,
    get_current_shift,
    list_shifts,
    open_shift,
    record_cash_movement,
)
from services.stock_service import ServiceError
from utils.auth import get_current_user, login_required, manager_required

bp = Blueprint("shifts", __name__, url_prefix="/api/shifts")


@bp.get("/current")
@login_required
def current_shift():
    shift = get_current_shift(get_current_user().id)
    return jsonify(shift.to_dict() if shift else None), 200


@bp.get("")
@manager_required
def all_shifts():
    return jsonify([shift.to_dict() for shift in list_shifts(request.args.get("status"))]), 200


@bp.post("/open")
@login_required
def start_shift():
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        shift = open_shift(user, payload.get("opening_cash", 0))
    except ServiceError as error:
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(shift.to_dict()), 201


@bp.post("/<int:shift_id>/cash-movements")
@login_required
def cash_movement(shift_id):
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        movement = record_cash_movement(
            shift_id,
            user,
            payload.get("direction"),
            payload.get("amount"),
            payload.get("note"),
        )
    except ServiceError as error:
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(movement.to_dict()), 201


@bp.post("/<int:shift_id>/close")
@login_required
def finish_shift(shift_id):
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        shift = close_shift(shift_id, user, payload.get("closing_cash"))
    except ServiceError as error:
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(shift.to_dict()), 200
