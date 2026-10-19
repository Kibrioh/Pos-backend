from .categories import bp as categories_bp
from .products import bp as products_bp
from .restocks import bp as restocks_bp
from .stock import bp as stock_bp
from .reports import bp as reports_bp
from .sales import bp as sales_bp
from .shifts import bp as shifts_bp
from .purchasing import suppliers_bp, purchase_orders_bp
from .audit import bp as audit_bp

__all__ = [
    "categories_bp",
    "products_bp",
    "restocks_bp",
    "stock_bp",
    "reports_bp",
    "sales_bp",
    "shifts_bp",
    "suppliers_bp",
    "purchase_orders_bp",
    "audit_bp",
]
