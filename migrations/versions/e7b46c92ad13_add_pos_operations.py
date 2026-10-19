"""add returns, barcode, shifts, purchasing, and audit data

Revision ID: e7b46c92ad13
Revises: c1d7e4a62f90
Create Date: 2026-10-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e7b46c92ad13"
down_revision = "c1d7e4a62f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_suppliers_name"),
    )

    op.create_table(
        "cashier_shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("opening_cash", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("closing_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_variance", sa.Numeric(12, 2), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_cashier_shifts_user_id", "cashier_shifts", ["user_id"])
    op.create_index("ix_cashier_shifts_status", "cashier_shifts", ["status"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ordered"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_created_by_id", "purchase_orders", ["created_by_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_order_items_quantity_positive"),
        sa.CheckConstraint("received_quantity >= 0", name="ck_purchase_order_items_received_nonnegative"),
        sa.CheckConstraint("received_quantity <= quantity", name="ck_purchase_order_items_received_lte_ordered"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_purchase_order_items_unit_cost_nonnegative"),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_purchase_order_items_purchase_order_id", "purchase_order_items", ["purchase_order_id"])
    op.create_index("ix_purchase_order_items_product_id", "purchase_order_items", ["product_id"])

    op.create_table(
        "cash_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_cash_movements_amount_positive"),
        sa.ForeignKeyConstraint(["shift_id"], ["cashier_shifts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_cash_movements_shift_id", "cash_movements", ["shift_id"])
    op.create_index("ix_cash_movements_user_id", "cash_movements", ["user_id"])

    op.create_table(
        "sale_returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), nullable=False),
        sa.Column("processed_by_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("refund_method", sa.String(length=30), nullable=False),
        sa.Column("refund_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("refund_total >= 0", name="ck_sale_returns_total_nonnegative"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["processed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shift_id"], ["cashier_shifts.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_sale_returns_sale_id", "sale_returns", ["sale_id"])
    op.create_index("ix_sale_returns_processed_by_id", "sale_returns", ["processed_by_id"])
    op.create_index("ix_sale_returns_shift_id", "sale_returns", ["shift_id"])

    op.create_table(
        "sale_return_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_return_id", sa.Integer(), nullable=False),
        sa.Column("sale_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("restock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("quantity > 0", name="ck_sale_return_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sale_return_items_price_nonnegative"),
        sa.ForeignKeyConstraint(["sale_return_id"], ["sale_returns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sale_item_id"], ["sale_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_sale_return_items_sale_return_id", "sale_return_items", ["sale_return_id"])
    op.create_index("ix_sale_return_items_sale_item_id", "sale_return_items", ["sale_item_id"])
    op.create_index("ix_sale_return_items_product_id", "sale_return_items", ["product_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("barcode", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))
        batch_op.create_index("ix_products_barcode", ["barcode"], unique=True)

    with op.batch_alter_table("sales") as batch_op:
        batch_op.add_column(sa.Column("shift_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_sales_shift_id", ["shift_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_sales_shift_id_cashier_shifts",
            "cashier_shifts",
            ["shift_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("sale_items") as batch_op:
        batch_op.add_column(sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))

    with op.batch_alter_table("restocks") as batch_op:
        batch_op.add_column(sa.Column("supplier_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_restocks_supplier_id", ["supplier_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_restocks_supplier_id_suppliers",
            "suppliers",
            ["supplier_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("restocks") as batch_op:
        batch_op.drop_constraint("fk_restocks_supplier_id_suppliers", type_="foreignkey")
        batch_op.drop_index("ix_restocks_supplier_id")
        batch_op.drop_column("supplier_id")

    with op.batch_alter_table("sale_items") as batch_op:
        batch_op.drop_column("unit_cost")

    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_constraint("fk_sales_shift_id_cashier_shifts", type_="foreignkey")
        batch_op.drop_index("ix_sales_shift_id")
        batch_op.drop_column("shift_id")

    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_index("ix_products_barcode")
        batch_op.drop_column("unit_cost")
        batch_op.drop_column("barcode")

    for table_name, index_names in [
        ("audit_logs", ["ix_audit_logs_created_at", "ix_audit_logs_entity_id", "ix_audit_logs_entity_type", "ix_audit_logs_action", "ix_audit_logs_actor_user_id"]),
        ("sale_return_items", ["ix_sale_return_items_product_id", "ix_sale_return_items_sale_item_id", "ix_sale_return_items_sale_return_id"]),
        ("sale_returns", ["ix_sale_returns_shift_id", "ix_sale_returns_processed_by_id", "ix_sale_returns_sale_id"]),
        ("cash_movements", ["ix_cash_movements_user_id", "ix_cash_movements_shift_id"]),
        ("purchase_order_items", ["ix_purchase_order_items_product_id", "ix_purchase_order_items_purchase_order_id"]),
        ("purchase_orders", ["ix_purchase_orders_status", "ix_purchase_orders_created_by_id", "ix_purchase_orders_supplier_id"]),
        ("cashier_shifts", ["ix_cashier_shifts_status", "ix_cashier_shifts_user_id"]),
        ("suppliers", []),
    ]:
        for index_name in index_names:
            op.drop_index(index_name, table_name=table_name)

    op.drop_table("audit_logs")
    op.drop_table("sale_return_items")
    op.drop_table("sale_returns")
    op.drop_table("cash_movements")
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
    op.drop_table("cashier_shifts")
    op.drop_table("suppliers")
