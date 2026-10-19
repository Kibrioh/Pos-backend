from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from extensions import db
from models import Product, Sale, SaleItem, SaleReturn, SaleReturnItem, User
from utils.auth import manager_required

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def filtered_sales_query():
    query = Sale.query

    try:
        start_text = request.args.get("start_date")
        end_text = request.args.get("end_date")
        start_date = date.fromisoformat(start_text) if start_text else None
        end_date = date.fromisoformat(end_text) if end_text else None
    except ValueError:
        return None, (
            jsonify(status="error", message="Dates must use YYYY-MM-DD format"),
            400,
        )

    if start_date and end_date and start_date > end_date:
        return None, (
            jsonify(status="error", message="start_date cannot be after end_date"),
            400,
        )

    if start_date:
        query = query.filter(
            Sale.created_at
            >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )

    if end_date:
        query = query.filter(
            Sale.created_at
            < datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=timezone.utc,
            )
        )

    return query, None


def money(value):
    return str(Decimal(str(value)))


def net_revenue_expression():
    refunded = (
        db.session.query(func.coalesce(func.sum(SaleReturn.refund_total), 0))
        .filter(SaleReturn.sale_id == Sale.id)
        .correlate(Sale)
        .scalar_subquery()
    )
    return Sale.total_amount - refunded


@bp.get("/summary")
@manager_required
def sales_summary():
    query, error = filtered_sales_query()
    if error:
        return error

    revenue, count = query.with_entities(
        func.coalesce(func.sum(net_revenue_expression()), 0),
        func.count(Sale.id),
    ).one()

    return jsonify(
        status="success",
        total_revenue=money(revenue),
        transaction_count=int(count),
    ), 200


@bp.get("/sales-by-cashier")
@manager_required
def sales_by_cashier():
    query, error = filtered_sales_query()
    if error:
        return error

    rows = query.join(User, User.id == Sale.user_id).with_entities(
        User.id.label("user_id"),
        User.username,
        User.name,
        func.sum(net_revenue_expression()).label("total_revenue"),
        func.count(Sale.id).label("transaction_count"),
    ).group_by(
        User.id, User.username, User.name
    ).order_by(func.sum(net_revenue_expression()).desc()).all()

    return jsonify(status="success", results=[
        {
            "user_id": row.user_id,
            "username": row.username,
            "name": row.name,
            "total_revenue": money(row.total_revenue),
            "transaction_count": int(row.transaction_count),
        }
        for row in rows
    ]), 200


@bp.get("/sales-by-date")
@manager_required
def sales_by_date():
    query, error = filtered_sales_query()
    if error:
        return error

    rows = query.with_entities(
        func.date(Sale.created_at).label("sale_date"),
        func.sum(net_revenue_expression()).label("total_revenue"),
        func.count(Sale.id).label("transaction_count"),
    ).group_by(
        func.date(Sale.created_at)
    ).order_by(func.date(Sale.created_at).asc()).all()

    return jsonify(status="success", results=[
        {
            "date": str(row.sale_date),
            "total_revenue": money(row.total_revenue),
            "transaction_count": int(row.transaction_count),
        }
        for row in rows
    ]), 200


@bp.get("/best-selling-products")
@manager_required
def best_selling_products():
    query, error = filtered_sales_query()
    if error:
        return error

    rows = query.join(
        SaleItem, SaleItem.sale_id == Sale.id
    ).join(
        Product, Product.id == SaleItem.product_id
    ).with_entities(
        Product.id.label("product_id"),
        Product.title.label("product_title"),
        func.sum(SaleItem.quantity).label("quantity_sold"),
        func.sum(SaleItem.subtotal).label("total_revenue"),
    ).group_by(
        Product.id, Product.title
    ).order_by(
        func.sum(SaleItem.quantity).desc(),
        Product.title.asc(),
    ).all()

    sale_ids = query.with_entities(Sale.id)
    returned_rows = (
        db.session.query(
            SaleReturnItem.product_id,
            func.sum(SaleReturnItem.quantity),
            func.sum(SaleReturnItem.unit_price * SaleReturnItem.quantity),
        )
        .join(SaleReturn, SaleReturn.id == SaleReturnItem.sale_return_id)
        .filter(SaleReturn.sale_id.in_(sale_ids))
        .group_by(SaleReturnItem.product_id)
        .all()
    )
    returned_by_product = {
        product_id: (int(quantity), Decimal(str(revenue)))
        for product_id, quantity, revenue in returned_rows
    }

    results = [
        {
            "product_id": row.product_id,
            "product_title": row.product_title,
            "quantity_sold": max(
                0,
                int(row.quantity_sold) - returned_by_product.get(row.product_id, (0, Decimal("0")))[0],
            ),
            "total_revenue": money(
                Decimal(str(row.total_revenue))
                - returned_by_product.get(row.product_id, (0, Decimal("0")))[1]
            ),
        }
        for row in rows
    ]
    results.sort(key=lambda result: (-result["quantity_sold"], result["product_title"]))
    return jsonify(status="success", results=results), 200


@bp.get("/dashboard")
@manager_required
def dashboard_summary():
    query, error = filtered_sales_query()
    if error:
        return error

    revenue, count = query.with_entities(
        func.coalesce(func.sum(net_revenue_expression()), 0),
        func.count(Sale.id),
    ).one()

    low_stock = Product.query.filter(
        Product.is_active.is_(True),
        Product.stock_quantity <= Product.low_stock_threshold
    ).order_by(
        Product.stock_quantity.asc(),
        Product.title.asc(),
    ).all()

    return jsonify(
        status="success",
        total_revenue=money(revenue),
        transaction_count=int(count),
        product_count=Product.query.filter(Product.is_active.is_(True)).count(),
        low_stock_count=len(low_stock),
        low_stock_products=[
            {
                "id": product.id,
                "title": product.title,
                "stock_quantity": product.stock_quantity,
                "low_stock_threshold": product.low_stock_threshold,
            }
            for product in low_stock
        ],
        cashier_count=User.query.filter_by(role="cashier").count(),
    ), 200


@bp.get("/gross-margin")
@manager_required
def gross_margin_summary():
    query, error = filtered_sales_query()
    if error:
        return error

    gross_margin = Decimal("0.00")
    net_revenue = Decimal("0.00")
    items_without_cost = 0
    for sale in query.all():
        net_revenue += Decimal(str(sale.total_amount))
        for sale_return in sale.returns:
            net_revenue -= Decimal(str(sale_return.refund_total))
        for item in sale.items:
            if item.unit_cost is None:
                items_without_cost += item.quantity
                continue
            gross_margin += (
                Decimal(str(item.unit_price)) - Decimal(str(item.unit_cost))
            ) * item.quantity
        for sale_return in sale.returns:
            for returned_item in sale_return.items:
                if returned_item.restock and returned_item.unit_cost is not None:
                    gross_margin += Decimal(str(returned_item.unit_cost)) * returned_item.quantity
                gross_margin -= Decimal(str(returned_item.unit_price)) * returned_item.quantity

    return jsonify(
        status="success",
        net_revenue=money(net_revenue),
        gross_margin=money(gross_margin),
        items_without_cost=items_without_cost,
    ), 200
