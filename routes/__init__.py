from .categories import bp as categories_bp
from .products import bp as products_bp
from .restocks import bp as restocks_bp
from .stock import bp as stock_bp
from .reports import bp as reports_bp
from .sales import bp as sales_bp

__all__ = [
    "categories_bp",
    "products_bp",
    "restocks_bp",
    "stock_bp",
    "reports_bp",
    "sales_bp",
]
