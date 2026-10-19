"""add product active status for safe archiving

Revision ID: c1d7e4a62f90
Revises: 7b876a3dd33a
Create Date: 2026-10-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c1d7e4a62f90"
down_revision = "7b876a3dd33a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade():
    op.drop_column("products", "is_active")
