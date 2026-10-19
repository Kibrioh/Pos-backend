from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload

from extensions import db
from models import Product, Restock, StockMovement, Supplier, User
from services.audit_service import add_audit_event


class ServiceError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------
# Read-only
# --------------------------------------------------

def get_all_stock():
    products = (
        Product.query
        .filter(Product.is_active.is_(True))
        .order_by(Product.title.asc())
        .all()
    )
    return [p.to_dict() for p in products]


def get_low_stock():
    products = (
        Product.query
        .filter(Product.is_active.is_(True))
        .filter(Product.stock_quantity > 0)
        .filter(Product.stock_quantity <= Product.low_stock_threshold)
        .order_by(Product.stock_quantity.asc())
        .all()
    )
    return [p.to_dict() for p in products]


def get_out_of_stock():
    products = (
        Product.query
        .filter(Product.is_active.is_(True))
        .filter(Product.stock_quantity <= 0)
        .order_by(Product.title.asc())
        .all()
    )
    return [p.to_dict() for p in products]


def get_movements():
    movements = (
        StockMovement.query
        .options(joinedload(StockMovement.user))
        .order_by(StockMovement.created_at.desc())
        .all()
    )
    return [m.to_dict() for m in movements]


def get_movements_for_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        raise ServiceError(f"Product {product_id} not found", 404)
    movements = (
        StockMovement.query
        .options(joinedload(StockMovement.user))
        .filter_by(product_id=product_id)
        .order_by(StockMovement.created_at.desc())
        .all()
    )
    return [m.to_dict() for m in movements]


def list_restocks():
    restocks = Restock.query.order_by(Restock.created_at.desc()).all()
    return [r.to_dict() for r in restocks]


def get_restock_by_id(restock_id):
    restock = db.session.get(Restock, restock_id)
    if not restock:
        raise ServiceError(f"Restock {restock_id} not found", 404)
    return restock.to_dict()


# --------------------------------------------------
# Writes
# --------------------------------------------------

def restock_product(payload, actor_id=None):
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")
    user_id = actor_id or payload.get("user_id")
    unit_cost_raw = payload.get("unit_cost")
    supplier = payload.get("supplier")
    invoice_number = payload.get("invoice_number")
    note = payload.get("note")

    _require_positive_int(product_id, "product_id")
    _require_positive_int(quantity, "quantity")
    _require_positive_int(user_id, "user_id")

    unit_cost = None
    if unit_cost_raw is not None:
        try:
            unit_cost = Decimal(str(unit_cost_raw))
        except (InvalidOperation, ValueError):
            raise ServiceError("unit_cost must be a valid number")
        if not unit_cost.is_finite() or unit_cost < 0:
            raise ServiceError("unit_cost cannot be negative")

    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        raise ServiceError(f"Product {product_id} not found or is inactive", 404)

    supplier_id = payload.get("supplier_id")
    supplier_record = None
    if supplier_id is not None:
        _require_positive_int(supplier_id, "supplier_id")
        supplier_record = db.session.get(Supplier, supplier_id)
        if not supplier_record or not supplier_record.is_active:
            raise ServiceError("Supplier not found or inactive", 404)

    user = db.session.get(User, user_id)
    if not user:
        raise ServiceError(f"User {user_id} not found", 404)

    before = product.stock_quantity
    after = before + quantity
    if unit_cost is not None:
        if before == 0:
            product.unit_cost = unit_cost
        elif product.unit_cost is not None:
            product.unit_cost = (
                (Decimal(str(product.unit_cost)) * before)
                + (unit_cost * quantity)
            ) / Decimal(after)
            product.unit_cost = product.unit_cost.quantize(Decimal("0.0001"))

    restock = Restock(
        product_id=product.id,
        supplier_id=supplier_record.id if supplier_record else None,
        user_id=user.id,
        quantity=quantity,
        unit_cost=unit_cost,
        supplier=supplier_record.name if supplier_record else supplier,
        invoice_number=invoice_number,
        note=note,
    )
    db.session.add(restock)
    db.session.flush()

    product.stock_quantity = after

    movement = StockMovement(
        product_id=product.id,
        user_id=user.id,
        movement_type="restock",
        quantity_delta=quantity,
        stock_before=before,
        stock_after=after,
        restock_id=restock.id,
        note=note or f"Linked to restock {restock.invoice_number or restock.id}",
    )
    db.session.add(movement)
    add_audit_event(user.id, "stock.restocked", "product", product.id, {
        "quantity": quantity,
        "stock_before": before,
        "stock_after": after,
        "unit_cost": str(unit_cost) if unit_cost is not None else None,
        "supplier_id": supplier_record.id if supplier_record else None,
    })
    db.session.commit()

    return {
        "restock": restock.to_dict(),
        "product": product.to_dict(),
        "movement": movement.to_dict(),
    }


def adjust_stock(payload, actor_id=None):
    product_id = payload.get("product_id")
    delta = payload.get("delta")
    user_id = actor_id or payload.get("user_id")
    note = payload.get("note")

    _require_positive_int(product_id, "product_id")
    _require_positive_int(user_id, "user_id")
    if not isinstance(delta, int) or delta == 0:
        raise ServiceError("Stock quantity change must be a non-zero whole number")

    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        raise ServiceError(f"Product {product_id} not found or is inactive", 404)

    user = db.session.get(User, user_id)
    if not user:
        raise ServiceError(f"User {user_id} not found", 404)

    before = product.stock_quantity
    after = before + delta
    if after < 0:
        raise ServiceError(
            f"Adjustment would put stock below zero ({before} -> {after})"
        )

    product.stock_quantity = after

    movement = StockMovement(
        product_id=product.id,
        user_id=user.id,
        movement_type="adjustment",
        quantity_delta=delta,
        stock_before=before,
        stock_after=after,
        note=note or None,
    )
    db.session.add(movement)
    add_audit_event(user.id, "stock.adjusted", "product", product.id, {
        "quantity_change": delta,
        "stock_before": before,
        "stock_after": after,
        "note": note or None,
    })
    db.session.commit()

    return {"product": product.to_dict(), "movement": movement.to_dict()}


def deduct_stock(product_id, quantity, user_id, sale_id=None, note=None):
    """
    Called internally by the sales service when a sale is completed.
    Does NOT commit — caller is responsible.
    """
    _require_positive_int(quantity, "quantity")
    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        raise ServiceError(f"Product {product_id} not found or is inactive", 404)

    if product.stock_quantity < quantity:
        raise ServiceError(
            f"Insufficient stock for '{product.title}': "
            f"requested {quantity}, available {product.stock_quantity}"
        )

    before = product.stock_quantity
    product.stock_quantity = before - quantity

    movement = StockMovement(
        product_id=product.id,
        user_id=user_id,
        movement_type="sale",
        quantity_delta=-quantity,
        stock_before=before,
        stock_after=product.stock_quantity,
        note=note or (f"Sale #{sale_id}" if sale_id else None),
    )
    db.session.add(movement)
    return movement


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _require_positive_int(value, field):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ServiceError(f"{field} must be a positive integer")


# --------------------------------------------------
# Restock: Update & Delete
# --------------------------------------------------

def update_restock(restock_id, payload, actor_id=None):
    """
    Update restock metadata (supplier, invoice_number, unit_cost, note).
    Quantity and product_id are immutable — delete and re-create instead.
    """
    restock = db.session.get(Restock, restock_id)
    if not restock:
        raise ServiceError(f"Restock {restock_id} not found", 404)

    if "quantity" in payload or "product_id" in payload or "user_id" in payload:
        raise ServiceError(
            "quantity, product_id, and user_id cannot be changed on a restock. "
            "Delete and re-create if you need to change them."
        )

    if "supplier" in payload:
        restock.supplier = payload["supplier"]
    if "invoice_number" in payload:
        restock.invoice_number = payload["invoice_number"]
    if "note" in payload:
        restock.note = payload["note"]

    if "unit_cost" in payload:
        raw = payload["unit_cost"]
        if raw is None:
            restock.unit_cost = None
        else:
            try:
                unit_cost = Decimal(str(raw))
            except (InvalidOperation, ValueError):
                raise ServiceError("unit_cost must be a valid number")
            if unit_cost < 0:
                raise ServiceError("unit_cost cannot be negative")
            restock.unit_cost = unit_cost

    add_audit_event(actor_id or restock.user_id, "restock.updated", "restock", restock.id, {
        "supplier": restock.supplier,
        "invoice_number": restock.invoice_number,
    })
    db.session.commit()
    return restock.to_dict()


def delete_restock(restock_id, actor_id=None):
    """
    Delete a restock, reversing its stock change with a compensating movement.
    Fails if reversing would push stock below zero (some units already sold).
    """
    restock = db.session.get(Restock, restock_id)
    if not restock:
        raise ServiceError(f"Restock {restock_id} not found", 404)

    product = db.session.get(Product, restock.product_id)
    if not product:
        raise ServiceError("Product for this restock no longer exists", 404)

    if product.stock_quantity < restock.quantity:
        raise ServiceError(
            f"Cannot delete: reversing would push stock below zero "
            f"(current {product.stock_quantity}, need to subtract {restock.quantity}). "
            f"Some units have already been sold."
        )

    before = product.stock_quantity
    after = before - restock.quantity
    product.stock_quantity = after

    reversal = StockMovement(
        product_id=product.id,
        user_id=restock.user_id,
        movement_type="adjustment",
        quantity_delta=-restock.quantity,
        stock_before=before,
        stock_after=after,
        note=(
            f"Reversal of deleted restock #{restock.id} "
            f"({restock.invoice_number or 'no invoice'})"
        ),
    )
    db.session.add(reversal)

    db.session.delete(restock)
    add_audit_event(actor_id or restock.user_id, "restock.deleted", "restock", restock_id, {
        "product_id": product.id,
        "quantity": restock.quantity,
    })
    db.session.commit()

    return {
        "deleted_restock_id": restock_id,
        "product": product.to_dict(),
        "reversal_movement": reversal.to_dict(),
    }
