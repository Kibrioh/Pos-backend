from collections import OrderedDict
from decimal import Decimal

from extensions import db
from models import CashMovement, CashierShift, Product, Sale, SaleItem, SaleReturn, SaleReturnItem, StockMovement
from services.audit_service import add_audit_event
from services.shift_service import expected_cash_for_shift
from services.stock_service import ServiceError

BASE_CURRENCY_QUANTUM = Decimal("0.0001")
REFUND_METHODS = {"cash", "card", "m-pesa"}


def create_return(actor, sale_id, payload):
    sale = Sale.query.filter_by(id=sale_id).with_for_update().first()
    if sale is None:
        raise ServiceError("Sale not found", 404)

    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ServiceError("A return reason is required")
    refund_method = str(payload.get("refund_method") or "").strip().lower()
    if refund_method not in REFUND_METHODS:
        raise ServiceError("Refund method must be cash, card, or m-pesa")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ServiceError("Select at least one item to return")

    requested = OrderedDict()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ServiceError("Each returned item must be an object")
        item_id = raw_item.get("sale_item_id")
        quantity = raw_item.get("quantity")
        if not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0:
            raise ServiceError("sale_item_id must be a positive integer")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ServiceError("Return quantity must be a positive integer")
        restock = raw_item.get("restock", False)
        if not isinstance(restock, bool):
            raise ServiceError("restock must be true or false")
        if item_id in requested:
            old_quantity, old_restock = requested[item_id]
            requested[item_id] = (old_quantity + quantity, old_restock or restock)
        else:
            requested[item_id] = (quantity, restock)

    sale_items = {
        item.id: item
        for item in SaleItem.query.filter_by(sale_id=sale.id)
        .with_for_update()
        .all()
    }
    existing_return_items = (
        db.session.query(SaleReturnItem.sale_item_id, db.func.sum(SaleReturnItem.quantity))
        .join(SaleReturn, SaleReturn.id == SaleReturnItem.sale_return_id)
        .filter(SaleReturn.sale_id == sale.id)
        .group_by(SaleReturnItem.sale_item_id)
        .all()
    )
    already_returned = {item_id: int(quantity) for item_id, quantity in existing_return_items}

    prepared = []
    total = Decimal("0.0000")
    for item_id, (quantity, restock) in requested.items():
        sale_item = sale_items.get(item_id)
        if sale_item is None:
            raise ServiceError(f"Sale item {item_id} does not belong to sale {sale_id}")
        remaining = sale_item.quantity - already_returned.get(item_id, 0)
        if quantity > remaining:
            raise ServiceError(
                f"Only {remaining} of '{sale_item.product.title}' can still be returned"
            )
        total += (Decimal(str(sale_item.unit_price)) * quantity).quantize(BASE_CURRENCY_QUANTUM)
        prepared.append((sale_item, quantity, restock))

    shift = None
    if refund_method == "cash":
        shift_id = payload.get("shift_id")
        if not isinstance(shift_id, int) or isinstance(shift_id, bool):
            raise ServiceError("Select an open till shift for cash refunds")
        shift = CashierShift.query.filter_by(id=shift_id, status="open").with_for_update().first()
        if shift is None:
            raise ServiceError("The selected till shift is not open", 409)
        if total > expected_cash_for_shift(shift):
            raise ServiceError("Cash refund exceeds the cash currently available in the till.", 409)

    return_record = SaleReturn(
        sale_id=sale.id,
        processed_by_id=actor.id,
        shift_id=shift.id if shift else None,
        reason=reason[:240],
        refund_method=refund_method,
        refund_total=total.quantize(BASE_CURRENCY_QUANTUM),
    )
    db.session.add(return_record)
    db.session.flush()

    for sale_item, quantity, restock in prepared:
        product = Product.query.filter_by(id=sale_item.product_id).with_for_update().first()
        db.session.add(SaleReturnItem(
            sale_return_id=return_record.id,
            sale_item_id=sale_item.id,
            product_id=sale_item.product_id,
            quantity=quantity,
            unit_price=sale_item.unit_price,
            unit_cost=sale_item.unit_cost,
            restock=restock,
        ))
        if restock and product is not None:
            before = product.stock_quantity
            if sale_item.unit_cost is not None:
                if before == 0:
                    product.unit_cost = sale_item.unit_cost
                elif product.unit_cost is not None:
                    product.unit_cost = (
                        (Decimal(str(product.unit_cost)) * before)
                        + (Decimal(str(sale_item.unit_cost)) * quantity)
                    ) / Decimal(before + quantity)
                    product.unit_cost = product.unit_cost.quantize(BASE_CURRENCY_QUANTUM)
            product.stock_quantity += quantity
            db.session.add(StockMovement(
                product_id=product.id,
                user_id=actor.id,
                movement_type="return",
                quantity_delta=quantity,
                stock_before=before,
                stock_after=product.stock_quantity,
                note=f"Returned from sale #{sale.id}",
            ))

    if refund_method == "cash":
        db.session.add(CashMovement(
            shift_id=shift.id,
            user_id=actor.id,
            direction="out",
            amount=total.quantize(BASE_CURRENCY_QUANTUM),
            note=f"Cash refund for sale #{sale.id}",
        ))
    add_audit_event(actor.id, "sale.returned", "sale_return", return_record.id, {
        "sale_id": sale.id,
        "refund_total": str(total.quantize(BASE_CURRENCY_QUANTUM)),
        "refund_method": refund_method,
        "reason": reason[:240],
        "item_count": len(prepared),
    })
    db.session.commit()
    return return_record
