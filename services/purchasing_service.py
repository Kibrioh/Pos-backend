from decimal import Decimal, InvalidOperation

from extensions import db
from models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    Restock,
    StockMovement,
    Supplier,
)
from services.audit_service import add_audit_event
from services.stock_service import ServiceError

BASE_CURRENCY_QUANTUM = Decimal("0.0001")


def _money(value, field):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ServiceError(f"{field} must be a valid amount") from error
    if not amount.is_finite() or amount < 0:
        raise ServiceError(f"{field} must be a non-negative amount")
    return amount.quantize(BASE_CURRENCY_QUANTUM)


def _positive_int(value, field):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ServiceError(f"{field} must be a positive integer")
    return value


def list_suppliers(active_only=True):
    query = Supplier.query.order_by(Supplier.name.asc())
    if active_only:
        query = query.filter_by(is_active=True)
    return query.all()


def create_supplier(actor, payload):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ServiceError("Supplier name is required")
    if Supplier.query.filter(db.func.lower(Supplier.name) == name.lower()).first():
        raise ServiceError("A supplier with this name already exists", 409)
    supplier = Supplier(
        name=name[:160],
        contact_name=str(payload.get("contact_name") or "").strip() or None,
        phone=str(payload.get("phone") or "").strip() or None,
        email=str(payload.get("email") or "").strip() or None,
    )
    db.session.add(supplier)
    db.session.flush()
    add_audit_event(actor.id, "supplier.created", "supplier", supplier.id, {"name": supplier.name})
    db.session.commit()
    return supplier


def list_purchase_orders():
    return PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).limit(200).all()


def create_purchase_order(actor, payload):
    supplier_id = _positive_int(payload.get("supplier_id"), "supplier_id")
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None or not supplier.is_active:
        raise ServiceError("Active supplier not found", 404)

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ServiceError("A purchase order needs at least one item")

    order = PurchaseOrder(
        supplier=supplier,
        created_by_id=actor.id,
        note=str(payload.get("note") or "").strip() or None,
    )
    db.session.add(order)
    db.session.flush()

    combined = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ServiceError("Each purchase order item must be an object")
        product_id = _positive_int(raw_item.get("product_id"), "product_id")
        quantity = _positive_int(raw_item.get("quantity"), "quantity")
        product = db.session.get(Product, product_id)
        if product is None or not product.is_active:
            raise ServiceError(f"Active product {product_id} not found", 404)
        unit_cost = _money(raw_item.get("unit_cost"), "unit_cost")
        if product_id in combined:
            old_quantity, old_cost = combined[product_id]
            if old_cost != unit_cost:
                raise ServiceError("Duplicate products must use the same unit cost")
            combined[product_id] = (old_quantity + quantity, unit_cost)
        else:
            combined[product_id] = (quantity, unit_cost)

    for product_id, (quantity, unit_cost) in combined.items():
        db.session.add(PurchaseOrderItem(
            purchase_order_id=order.id,
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost,
        ))

    db.session.flush()
    add_audit_event(actor.id, "purchase_order.created", "purchase_order", order.id, {
        "supplier_id": supplier.id,
        "item_count": len(combined),
    })
    db.session.commit()
    return order


def _update_average_cost(product, received_quantity, unit_cost):
    old_quantity = product.stock_quantity
    if old_quantity == 0 or product.unit_cost is None:
        product.unit_cost = unit_cost if old_quantity == 0 else None
        return
    total_quantity = old_quantity + received_quantity
    product.unit_cost = (
        (Decimal(str(product.unit_cost)) * old_quantity)
        + (unit_cost * received_quantity)
    ) / Decimal(total_quantity)
    product.unit_cost = product.unit_cost.quantize(BASE_CURRENCY_QUANTUM)


def receive_purchase_order(actor, order_id, payload):
    order = PurchaseOrder.query.filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise ServiceError("Purchase order not found", 404)
    if order.status in {"received", "cancelled"}:
        raise ServiceError(f"Cannot receive a {order.status} purchase order", 409)

    raw_items = payload.get("items")
    if raw_items is None:
        raw_items = [
            {"purchase_order_item_id": item.id, "quantity": item.quantity - item.received_quantity}
            for item in order.items
            if item.received_quantity < item.quantity
        ]
    if not isinstance(raw_items, list) or not raw_items:
        raise ServiceError("There are no outstanding items to receive")

    received_lines = []
    seen = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ServiceError("Each received item must be an object")
        item_id = _positive_int(raw_item.get("purchase_order_item_id"), "purchase_order_item_id")
        quantity = _positive_int(raw_item.get("quantity"), "quantity")
        if item_id in seen:
            raise ServiceError("Each purchase order line can only be listed once")
        seen.add(item_id)
        line = PurchaseOrderItem.query.filter_by(
            id=item_id,
            purchase_order_id=order.id,
        ).with_for_update().first()
        if line is None:
            raise ServiceError(f"Purchase order line {item_id} not found", 404)
        outstanding = line.quantity - line.received_quantity
        if quantity > outstanding:
            raise ServiceError(
                f"Cannot receive {quantity}; line {item_id} has {outstanding} outstanding"
            )
        product = Product.query.filter_by(id=line.product_id).with_for_update().first()
        if product is None or not product.is_active:
            raise ServiceError(f"Product for purchase order line {item_id} is inactive", 409)
        received_lines.append((line, product, quantity))

    for line, product, quantity in received_lines:
        before = product.stock_quantity
        _update_average_cost(product, quantity, Decimal(str(line.unit_cost)))
        product.stock_quantity += quantity
        line.received_quantity += quantity
        restock = Restock(
            product_id=product.id,
            supplier_id=order.supplier_id,
            user_id=actor.id,
            quantity=quantity,
            unit_cost=line.unit_cost,
            supplier=order.supplier.name,
            invoice_number=f"PO-{order.id}",
            note=f"Received against purchase order #{order.id}",
        )
        db.session.add(restock)
        db.session.flush()
        db.session.add(StockMovement(
            product_id=product.id,
            user_id=actor.id,
            movement_type="restock",
            quantity_delta=quantity,
            stock_before=before,
            stock_after=product.stock_quantity,
            restock_id=restock.id,
            note=f"Purchase order #{order.id}",
        ))
    db.session.flush()

    remaining = sum(item.quantity - item.received_quantity for item in order.items)
    order.status = "received" if remaining == 0 else "partially_received"
    add_audit_event(actor.id, "purchase_order.received", "purchase_order", order.id, {
        "received_quantities": [
            {"purchase_order_item_id": line.id, "quantity": quantity}
            for line, _product, quantity in received_lines
        ],
        "status": order.status,
    })
    db.session.commit()
    return order
