"""source_images.order_index — user-controlled display order per variant

Revision ID: b6e02f78c40d
Revises: a8c93e1d2f15
Create Date: 2026-05-15 06:00:00.000000

加 order_index 列，回填按 created_at 升序（保留现有视觉顺序），前端 reorder
endpoint 后续会整体覆写。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6e02f78c40d"
down_revision: Union[str, Sequence[str], None] = "a8c93e1d2f15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite 需要 batch_alter；先加列（带 default 0）
    with op.batch_alter_table("source_images") as batch:
        batch.add_column(sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))

    # 回填：按 variant_id 分组，按 created_at 排序赋 0..N-1
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, variant_id FROM source_images "
            "ORDER BY variant_id, created_at, id"
        )
    ).fetchall()
    last_variant = None
    idx = 0
    for r in rows:
        if r.variant_id != last_variant:
            last_variant = r.variant_id
            idx = 0
        conn.execute(
            sa.text("UPDATE source_images SET order_index = :ix WHERE id = :id"),
            {"ix": idx, "id": r.id},
        )
        idx += 1


def downgrade() -> None:
    with op.batch_alter_table("source_images") as batch:
        batch.drop_column("order_index")
