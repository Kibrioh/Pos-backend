from decimal import Decimal

from sqlalchemy import text

from app import create_app
from extensions import db
from models import (
    User,
    Category,
    Product,
    Sale,
    SaleItem,
    StockMovement,
)


app = create_app()

with app.app_context():
    try:
        #This deletes all records in these tables.
        db.session.execute(
            text("""
                TRUNCATE TABLE
                    stock_movements,
                    sale_items,
                    sales,
                    products,
                    categories,
                    users
                RESTART IDENTITY CASCADE
            """)
        )

        # --------------------------------------------------
        # 1. USERS
        # --------------------------------------------------
        manager = User(
            username="manager",
            name="Demo Manager",
            role="manager",
        )
        manager.set_password("Manager123!")

        cashier = User(
            username="cashier",
            name="Demo Cashier",
            role="cashier",
        )
        cashier.set_password("Cashier123!")

        db.session.add_all([manager, cashier])
        db.session.flush()

        # --------------------------------------------------
        # 2. CATEGORIES
        # --------------------------------------------------
        groceries = Category(name="Groceries")
        beverages = Category(name="Beverages")
        household = Category(name="Household")

        db.session.add_all([groceries, beverages, household])
        db.session.flush()

        # --------------------------------------------------
        # 3. PRODUCTS
        # --------------------------------------------------
        flour = Product(
            title="Maize Flour 2kg",
            brand="Generic",
            price=Decimal("180.00"),
            stock_quantity=30,
            low_stock_threshold=5,
            category=groceries,
            thumbnail="products/maize-flour.webp",
            description="Two-kilogram packet of maize flour.",
        )

        water = Product(
            title="Bottled Water 1L",
            brand="Generic",
            price=Decimal("60.00"),
            stock_quantity=50,
            low_stock_threshold=10,
            category=beverages,
            thumbnail="products/bottled-water.webp",
            description="One-litre bottle of drinking water.",
        )

        soap = Product(
            title="Laundry Soap",
            brand="Generic",
            price=Decimal("120.00"),
            stock_quantity=20,
            low_stock_threshold=5,
            category=household,
            thumbnail="products/laundry-soap.webp",
            description="Laundry soap bar.",
        )

        db.session.add_all([flour, water, soap])
        db.session.flush()

        # --------------------------------------------------
        # 4. INITIAL STOCK MOVEMENTS
        # --------------------------------------------------
        products = [flour, water, soap]

        for product in products:
            db.session.add(
                StockMovement(
                    product=product,
                    user=manager,
                    movement_type="initial_stock",
                    quantity_delta=product.stock_quantity,
                    stock_before=0,
                    stock_after=product.stock_quantity,
                    note="Initial stock created by development seed.",
                )
            )

        # --------------------------------------------------
        # 5. SAMPLE SALE AND SALE ITEMS
        # --------------------------------------------------
        sale_lines = [
            (flour, 2),
            (water, 3),
            (soap, 1),
        ]

        total_amount = Decimal("0.00")
        sale_details = []

        # Calculate totals and prepare stock deductions.
        for product, quantity in sale_lines:
            if quantity <= 0:
                raise ValueError(
                    f"Invalid quantity for {product.title}"
                )

            if product.stock_quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for {product.title}"
                )

            stock_before = product.stock_quantity
            stock_after = stock_before - quantity
            subtotal = product.price * quantity

            total_amount += subtotal

            sale_details.append(
                (
                    product,
                    quantity,
                    stock_before,
                    stock_after,
                    subtotal,
                )
            )

            product.stock_quantity = stock_after

        sale = Sale(
            user=cashier,
            total_amount=total_amount,
            payment_method="cash",
        )

        db.session.add(sale)
        db.session.flush()

        # --------------------------------------------------
        # 6. SALE ITEMS AND SALE STOCK MOVEMENTS
        # --------------------------------------------------
        for (
            product,
            quantity,
            stock_before,
            stock_after,
            subtotal,
        ) in sale_details:

            db.session.add(
                SaleItem(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    subtotal=subtotal,
                )
            )

            db.session.add(
                StockMovement(
                    product=product,
                    user=cashier,
                    movement_type="sale",
                    quantity_delta=-quantity,
                    stock_before=stock_before,
                    stock_after=stock_after,
                    note=f"Stock deducted for seeded sale #{sale.id}.",
                )
            )

        # --------------------------------------------------
        # 7. COMMIT ALL CHANGES
        # --------------------------------------------------
        db.session.commit()

        print("Database seeded successfully!")
        print("Users: manager, cashier")
        print("Categories: 3")
        print("Products: 3")
        print("Sample sales: 1")
        print("Sale items: 3")
        print("Stock movements: 6")
        print(f"Sample sale total: {total_amount}")

    except Exception:
        db.session.rollback()
        raise