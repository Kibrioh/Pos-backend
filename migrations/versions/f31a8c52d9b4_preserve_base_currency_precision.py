"""preserve precision for prices converted from KSh

Revision ID: f31a8c52d9b4
Revises: e7b46c92ad13
Create Date: 2026-10-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f31a8c52d9b4"
down_revision = "e7b46c92ad13"
branch_labels = None
depends_on = None


MONEY_COLUMNS = {
    "products": [("price", False), ("unit_cost", True)],
    "sales": [("total_amount", False)],
    "sale_items": [
        ("unit_price", False),
        ("unit_cost", True),
        ("subtotal", False),
    ],
    "restocks": [("unit_cost", True)],
    "purchase_order_items": [("unit_cost", False)],
    "cashier_shifts": [
        ("opening_cash", False),
        ("closing_cash", True),
        ("expected_cash", True),
        ("cash_variance", True),
    ],
    "cash_movements": [("amount", False)],
    "sale_returns": [("refund_total", False)],
    "sale_return_items": [("unit_price", False), ("unit_cost", True)],
}


def _set_scale(existing_scale, new_scale):
    for table_name, columns in MONEY_COLUMNS.items():
        with op.batch_alter_table(table_name) as batch_op:
            for column_name, nullable in columns:
                batch_op.alter_column(
                    column_name,
                    existing_type=sa.Numeric(12, existing_scale),
                    type_=sa.Numeric(12, new_scale),
                    existing_nullable=nullable,
                )


def upgrade():
    _set_scale(2, 4)


def downgrade():
    _set_scale(4, 2)
