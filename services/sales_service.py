from collections import OrderedDict
from decimal import Decimal

from extensions import db
from models import Product, Sale, SaleItem, User
from services.stock_service import ServiceError, deduct_stock

TWO_PLACES = Decimal("0.01")


def _clean_items(raw_items):
    """Validate the request items and merge duplicates: product_id -> total quantity."""
    if not isinstance(raw_items, list) or not raw_items:
        raise ServiceError("A sale needs at least one item.")

    wanted = OrderedDict()
    for entry in raw_items:
        if not isinstance(entry, dict):
            raise ServiceError("Each item needs a product_id and a quantity.")
        product_id = entry.get("product_id")
        quantity = entry.get("quantity")
        for value in (product_id, quantity):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ServiceError("product_id and quantity must be integers.")
        if quantity <= 0:
            raise ServiceError("Quantity must be greater than zero.")
        wanted[product_id] = wanted.get(product_id, 0) + quantity
    return wanted


def create_sale(user_id, raw_items, payment_method="cash"):
    wanted = _clean_items(raw_items)

    try:
        user = db.session.get(User, user_id)
        if user is None:
            raise ServiceError("Cashier not found.", 401)

        # Lock these product rows until we commit or roll back, so two cashiers
        # can't both sell the last unit. Sorting by id avoids deadlocks.
        products = (
            Product.query.filter(Product.id.in_(list(wanted)))
            .order_by(Product.id)
            .populate_existing()
            .with_for_update()
            .all()
        )
        by_id = {p.id: p for p in products}

        # Check everything first, so the cashier sees all problems at once.
        problems = []
        for product_id, qty in wanted.items():
            product = by_id.get(product_id)
            if product is None:
                problems.append(f"Product {product_id} not found.")
            elif product.stock_quantity < qty:
                problems.append(
                    f"Not enough stock for '{product.title}': "
                    f"requested {qty}, available {product.stock_quantity}."
                )
        if problems:
            raise ServiceError(" ".join(problems), 409)

        sale = Sale(user_id=user.id, payment_method=payment_method)
        db.session.add(sale)
        db.session.flush()  # gets sale.id without committing yet

        total = Decimal("0.00")
        for product_id, qty in wanted.items():
            product = by_id[product_id]
            unit_price = product.price  # always from the database, never the client
            subtotal = (unit_price * qty).quantize(TWO_PLACES)
            total += subtotal

            db.session.add(SaleItem(
                sale_id=sale.id, product_id=product.id,
                quantity=qty, unit_price=unit_price, subtotal=subtotal,
            ))
            # The team's helper lowers stock and records the stock movement.
            # It does not commit; we do that once below.
            deduct_stock(product.id, qty, user.id, sale_id=sale.id)

        sale.total_amount = total
        db.session.commit()  # sale, items, stock and audit rows all succeed together
        return sale

    except Exception:
        db.session.rollback()  # any failure undoes everything and releases the locks
        raise
