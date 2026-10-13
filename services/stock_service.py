from extensions import db
from models import Product, StockMovement, User


class ServiceError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def get_all_stock():
    products = Product.query.order_by(Product.title.asc()).all()
    return [p.to_dict() for p in products]


def get_low_stock():
    products = (
        Product.query
        .filter(Product.stock_quantity > 0)
        .filter(Product.stock_quantity <= Product.low_stock_threshold)
        .order_by(Product.stock_quantity.asc())
        .all()
    )
    return [p.to_dict() for p in products]


def get_out_of_stock():
    products = (
        Product.query
        .filter(Product.stock_quantity <= 0)
        .order_by(Product.title.asc())
        .all()
    )
    return [p.to_dict() for p in products]


def get_movements():
    movements = StockMovement.query.order_by(StockMovement.created_at.desc()).all()
    return [m.to_dict() for m in movements]


def get_movements_for_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        raise ServiceError(f"Product {product_id} not found", 404)
    movements = (
        StockMovement.query
        .filter_by(product_id=product_id)
        .order_by(StockMovement.created_at.desc())
        .all()
    )
    return [m.to_dict() for m in movements]


def restock_product(payload):
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")
    user_id = payload.get("user_id")
    note = payload.get("note")

    _require_positive_int(product_id, "product_id")
    _require_positive_int(quantity, "quantity")
    _require_positive_int(user_id, "user_id")

    product = db.session.get(Product, product_id)
    if not product:
        raise ServiceError(f"Product {product_id} not found", 404)
    user = db.session.get(User, user_id)
    if not user:
        raise ServiceError(f"User {user_id} not found", 404)

    before = product.stock_quantity
    product.stock_quantity = before + quantity

    movement = StockMovement(
        product_id=product.id,
        user_id=user.id,
        movement_type="restock",
        quantity_delta=quantity,
        stock_before=before,
        stock_after=product.stock_quantity,
        note=note or None,
    )
    db.session.add(movement)
    db.session.commit()

    return {"product": product.to_dict(), "movement": movement.to_dict()}


def adjust_stock(payload):
    product_id = payload.get("product_id")
    delta = payload.get("delta")
    user_id = payload.get("user_id")
    note = payload.get("note")

    _require_positive_int(product_id, "product_id")
    _require_positive_int(user_id, "user_id")
    if not isinstance(delta, int) or delta == 0:
        raise ServiceError("delta must be a non-zero integer")

    product = db.session.get(Product, product_id)
    if not product:
        raise ServiceError(f"Product {product_id} not found", 404)
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
    db.session.commit()

    return {"product": product.to_dict(), "movement": movement.to_dict()}


def deduct_stock(product_id, quantity, user_id, sale_id=None, note=None):
    """
    Called internally by the sales service when a sale is completed.
    Returns the StockMovement (caller is responsible for committing).
    """
    _require_positive_int(quantity, "quantity")
    product = db.session.get(Product, product_id)
    if not product:
        raise ServiceError(f"Product {product_id} not found", 404)

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


def _require_positive_int(value, field):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ServiceError(f"{field} must be a positive integer")
