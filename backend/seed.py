from backend.app import create_app
from backend.extensions import db
from backend.models import Category, Product


def seed_database():
    app = create_app()
    with app.app_context():
        if Category.query.count() == 0:
            office = Category(name="Office", description="Office supplies and accessories")
            electronics = Category(name="Electronics", description="Electronic devices and accessories")
            db.session.add_all([office, electronics])
            db.session.commit()

        if Product.query.count() == 0:
            office_products = [
                Product(name="Notebook", sku="NB-001", description="A4 ruled notebook", price=120.00, stock_quantity=45, category_id=1),
                Product(name="Pens Pack", sku="PEN-002", description="Pack of 10 blue pens", price=80.00, stock_quantity=60, category_id=1),
            ]
            electronics_products = [
                Product(name="Wireless Mouse", sku="MOUSE-101", description="USB wireless mouse", price=1200.00, stock_quantity=18, category_id=2),
                Product(name="Mechanical Keyboard", sku="KB-220", description="Compact mechanical keyboard", price=3600.00, stock_quantity=12, category_id=2),
            ]
            db.session.add_all(office_products + electronics_products)
            db.session.commit()


if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")
