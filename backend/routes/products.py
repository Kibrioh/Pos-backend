from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models import Category, Product

bp = Blueprint("products", __name__, url_prefix="/api/products")


@bp.get("")
def get_products():
    products = Product.query.order_by(Product.name.asc()).all()
    return jsonify([product.to_dict() for product in products])


@bp.get("/<int:product_id>")
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict())


@bp.post("")
def create_product():
    payload = request.get_json(silent=True) or {}

    name = (payload.get("name") or "").strip()
    sku = (payload.get("sku") or "").strip()
    if not name or not sku:
        return jsonify({"error": "Product name and SKU are required."}), 400

    if Product.query.filter_by(sku=sku).first():
        return jsonify({"error": "Product with this SKU already exists."}), 409

    category_id = payload.get("category_id")
    category = Category.query.get(category_id)
    if category is None:
        return jsonify({"error": "Invalid category reference."}), 400

    try:
        price = Decimal(str(payload.get("price")))
    except (InvalidOperation, TypeError, ValueError):
        return jsonify({"error": "Price must be a valid number."}), 400

    if price < 0:
        return jsonify({"error": "Price cannot be negative."}), 400

    stock_quantity = payload.get("stock_quantity", 0)
    try:
        stock_quantity = int(stock_quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "Stock quantity must be an integer."}), 400

    if stock_quantity < 0:
        return jsonify({"error": "Stock quantity cannot be negative."}), 400

    product = Product(
        name=name,
        sku=sku,
        description=payload.get("description"),
        price=price,
        stock_quantity=stock_quantity,
        category_id=category.id,
    )

    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@bp.put("/<int:product_id>")
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    payload = request.get_json(silent=True) or {}

    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Product name cannot be empty."}), 400
        product.name = name

    if "sku" in payload:
        sku = (payload.get("sku") or "").strip()
        if not sku:
            return jsonify({"error": "SKU cannot be empty."}), 400
        if Product.query.filter(Product.id != product_id, Product.sku == sku).first():
            return jsonify({"error": "Product with this SKU already exists."}), 409
        product.sku = sku

    if "description" in payload:
        product.description = payload.get("description")

    if "price" in payload:
        try:
            price = Decimal(str(payload.get("price")))
        except (InvalidOperation, TypeError, ValueError):
            return jsonify({"error": "Price must be a valid number."}), 400
        if price < 0:
            return jsonify({"error": "Price cannot be negative."}), 400
        product.price = price

    if "stock_quantity" in payload:
        try:
            stock_quantity = int(payload.get("stock_quantity"))
        except (TypeError, ValueError):
            return jsonify({"error": "Stock quantity must be an integer."}), 400
        if stock_quantity < 0:
            return jsonify({"error": "Stock quantity cannot be negative."}), 400
        product.stock_quantity = stock_quantity

    if "category_id" in payload:
        category = Category.query.get(payload.get("category_id"))
        if category is None:
            return jsonify({"error": "Invalid category reference."}), 400
        product.category_id = category.id

    if "is_active" in payload:
        product.is_active = bool(payload.get("is_active"))

    db.session.commit()
    return jsonify(product.to_dict())


@bp.delete("/<int:product_id>")
def deactivate_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    return jsonify({"message": "Product deactivated successfully.", "product": product.to_dict()})
