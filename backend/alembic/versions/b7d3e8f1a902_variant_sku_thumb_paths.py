"""variant.sku_thumb_paths (JSON list, multi-candidate SKU 色卡)

把原本单值 sku_thumb_path 演进为多候选 list。第一项为主色卡，其余为备选。

Revision ID: b7d3e8f1a902
Revises: a4f2c1d39e88
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d3e8f1a902"
down_revision: Union[str, Sequence[str], None] = "a4f2c1d39e88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("variants") as batch_op:
        batch_op.add_column(
            sa.Column("sku_thumb_paths", sa.JSON(), nullable=False, server_default="[]")
        )

    # Migrate existing single-value sku_thumb_path → 单项列表
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE variants SET sku_thumb_paths = json_array(sku_thumb_path) "
        "WHERE sku_thumb_path IS NOT NULL AND sku_thumb_path != ''"
    ))


def downgrade() -> None:
    with op.batch_alter_table("variants") as batch_op:
        batch_op.drop_column("sku_thumb_paths")
