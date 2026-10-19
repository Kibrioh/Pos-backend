from flask import Blueprint, jsonify, request

from extensions import db
from services.shift_service import (
    close_shift,
    assign_shift,
    expected_cash_for_shift,
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
    if shift is None:
        return jsonify(None), 200
    data = shift.to_dict()
    data["expected_cash"] = str(expected_cash_for_shift(shift))
    return jsonify(data), 200


@bp.get("")
@manager_required
def all_shifts():
    shifts = list_shifts(request.args.get("status"))
    results = []
    for shift in shifts:
        data = shift.to_dict()
        if shift.status == "open":
            data["expected_cash"] = str(expected_cash_for_shift(shift))
        results.append(data)
    return jsonify(results), 200


@bp.post("/open")
@manager_required
def start_shift():
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        shift = open_shift(user, payload.get("opening_cash", 0))
    except ServiceError as error:
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(shift.to_dict()), 201


@bp.post("/assign")
@manager_required
def assign_cashier_float():
    manager = get_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        shift = assign_shift(
            manager,
            payload.get("cashier_id"),
            payload.get("opening_cash"),
        )
    except ServiceError as error:
        db.session.rollback()
        return jsonify(status="error", message=str(error)), error.status_code
    return jsonify(shift.to_dict()), 201


@bp.post("/<int:shift_id>/cash-movements")
@manager_required
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
