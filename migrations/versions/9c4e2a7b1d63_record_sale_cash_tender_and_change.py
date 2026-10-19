"""record cash tender and change on sales

Revision ID: 9c4e2a7b1d63
Revises: f31a8c52d9b4
Create Date: 2026-10-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9c4e2a7b1d63"
down_revision = "f31a8c52d9b4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sales", sa.Column("amount_tendered", sa.Numeric(12, 4), nullable=True))
    op.add_column(
        "sales",
        sa.Column(
            "change_given",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="0.0000",
        ),
    )
    op.create_check_constraint(
        "ck_sales_tendered_nonnegative",
        "sales",
        "amount_tendered IS NULL OR amount_tendered >= 0",
    )
    op.create_check_constraint(
        "ck_sales_change_nonnegative",
        "sales",
        "change_given >= 0",
    )
    op.alter_column("sales", "change_given", server_default=None)


def downgrade():
    op.drop_constraint("ck_sales_change_nonnegative", "sales", type_="check")
    op.drop_constraint("ck_sales_tendered_nonnegative", "sales", type_="check")
    op.drop_column("sales", "change_given")
    op.drop_column("sales", "amount_tendered")
