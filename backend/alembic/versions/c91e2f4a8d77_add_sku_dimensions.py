"""add SKU dimensions (length/width/height in cm)

Revision ID: c91e2f4a8d77
Revises: f3aaa1c81f2b
Create Date: 2026-05-10 23:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c91e2f4a8d77"
down_revision: Union[str, Sequence[str], None] = "f3aaa1c81f2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("skus") as batch_op:
        batch_op.add_column(sa.Column("length_cm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("width_cm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("height_cm", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("skus") as batch_op:
        batch_op.drop_column("height_cm")
        batch_op.drop_column("width_cm")
        batch_op.drop_column("length_cm")
