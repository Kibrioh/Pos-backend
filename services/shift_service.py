from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from extensions import db
from models import CashierShift, CashMovement, Sale, User
from services.audit_service import add_audit_event
from services.stock_service import ServiceError

BASE_CURRENCY_QUANTUM = Decimal("0.0001")


def parse_cash(value, field):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ServiceError(f"{field} must be a valid amount") from error
    if not amount.is_finite() or amount < 0:
        raise ServiceError(f"{field} must be a non-negative amount")
    return amount.quantize(BASE_CURRENCY_QUANTUM)


def get_current_shift(user_id, lock=False):
    query = CashierShift.query.filter_by(user_id=user_id, status="open")
    if lock:
        query = query.with_for_update()
    return query.first()


def list_shifts(status=None):
    query = CashierShift.query.order_by(CashierShift.opened_at.desc())
    if status:
        query = query.filter_by(status=status)
    return query.limit(200).all()


def open_shift(user, opening_cash):
    amount = parse_cash(opening_cash, "Opening cash")
    db.session.query(User.id).filter_by(id=user.id).with_for_update().first()
    if get_current_shift(user.id):
        raise ServiceError("You already have an open shift.", 409)

    shift = CashierShift(user_id=user.id, opening_cash=amount, status="open")
    db.session.add(shift)
    db.session.flush()
    add_audit_event(user.id, "shift.opened", "cashier_shift", shift.id, {
        "opening_cash": str(amount),
    })
    db.session.commit()
    return shift


def assign_shift(manager, cashier_id, opening_cash):
    """Assign an opening float to a cashier by opening their till shift."""
    if not isinstance(cashier_id, int) or isinstance(cashier_id, bool) or cashier_id <= 0:
        raise ServiceError("Select a valid cashier")

    amount = parse_cash(opening_cash, "Opening float")
    cashier = User.query.filter_by(id=cashier_id).with_for_update().first()
    if cashier is None or cashier.role != "cashier":
        raise ServiceError("Cashier not found", 404)
    if get_current_shift(cashier.id):
        raise ServiceError("This cashier already has an open shift", 409)

    shift = CashierShift(user_id=cashier.id, opening_cash=amount, status="open")
    db.session.add(shift)
    db.session.flush()
    add_audit_event(manager.id, "shift.float_assigned", "cashier_shift", shift.id, {
        "cashier_id": cashier.id,
        "opening_cash": str(amount),
    })
    db.session.commit()
    return shift


def _get_shift_for_actor(shift_id, actor, allow_manager=True):
    shift = CashierShift.query.filter_by(id=shift_id).with_for_update().first()
    if shift is None:
        raise ServiceError("Shift not found", 404)
    if shift.user_id != actor.id and not (allow_manager and actor.role == "manager"):
        raise ServiceError("You do not have access to this shift", 403)
    if shift.status != "open":
        raise ServiceError("This shift is already closed", 409)
    return shift


def record_cash_movement(shift_id, actor, direction, amount, note):
    if direction not in {"in", "out"}:
        raise ServiceError("Direction must be 'in' or 'out'")
    amount = parse_cash(amount, "Amount")
    if amount <= 0:
        raise ServiceError("Amount must be greater than zero")
    note = str(note or "").strip()
    if not note:
        raise ServiceError("A reason is required for a cash movement")

    shift = _get_shift_for_actor(shift_id, actor)
    if direction == "out" and amount > expected_cash_for_shift(shift):
        raise ServiceError("Cash out cannot exceed the cash currently available in the till.", 409)

    movement = CashMovement(
        shift_id=shift.id,
        user_id=actor.id,
        direction=direction,
        amount=amount,
        note=note[:240],
    )
    db.session.add(movement)
    db.session.flush()
    add_audit_event(actor.id, f"shift.cash_{direction}", "cash_movement", movement.id, {
        "cashier_id": shift.user_id,
        "shift_id": shift.id,
        "amount": str(amount),
        "note": note[:240],
    })
    db.session.commit()
    return movement


def expected_cash_for_shift(shift):
    sales_total = db.session.query(db.func.coalesce(db.func.sum(Sale.total_amount), 0)).filter(
        Sale.shift_id == shift.id,
        db.func.lower(Sale.payment_method) == "cash",
    ).scalar()
    inflows = db.session.query(db.func.coalesce(db.func.sum(CashMovement.amount), 0)).filter_by(
        shift_id=shift.id,
        direction="in",
    ).scalar()
    outflows = db.session.query(db.func.coalesce(db.func.sum(CashMovement.amount), 0)).filter_by(
        shift_id=shift.id,
        direction="out",
    ).scalar()
    return (
        Decimal(str(shift.opening_cash or 0))
        + Decimal(str(sales_total or 0))
        + Decimal(str(inflows or 0))
        - Decimal(str(outflows or 0))
    ).quantize(BASE_CURRENCY_QUANTUM)


def close_shift(shift_id, actor, closing_cash):
    shift = _get_shift_for_actor(shift_id, actor)
    closing = parse_cash(closing_cash, "Closing cash")
    expected = expected_cash_for_shift(shift)
    shift.closing_cash = closing
    shift.expected_cash = expected
    shift.cash_variance = (closing - expected).quantize(BASE_CURRENCY_QUANTUM)
    shift.closed_at = datetime.now(timezone.utc)
    shift.status = "closed"
    add_audit_event(actor.id, "shift.closed", "cashier_shift", shift.id, {
        "expected_cash": str(expected),
        "closing_cash": str(closing),
        "cash_variance": str(shift.cash_variance),
    })
    db.session.commit()
    return shift
