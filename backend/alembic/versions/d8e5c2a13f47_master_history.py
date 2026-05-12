"""source_image.master_history — keep all generated versions per ratio

Revision ID: d8e5c2a13f47
Revises: b7d3e8f1a902
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e5c2a13f47"
down_revision: Union[str, Sequence[str], None] = "b7d3e8f1a902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.add_column(
            sa.Column("master_history", sa.JSON(), nullable=False, server_default="{}")
        )

    # 把已有 master_paths 的每个 ratio 当成首版本初始化 history
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, master_paths FROM source_images")).fetchall()
    import json
    for r in rows:
        try:
            mp = json.loads(r[1]) if isinstance(r[1], str) else (r[1] or {})
        except Exception:
            mp = {}
        if not mp:
            continue
        hist = {k: [v] for k, v in mp.items() if v}
        bind.execute(
            sa.text("UPDATE source_images SET master_history = :h WHERE id = :i"),
            {"h": json.dumps(hist, ensure_ascii=False), "i": r[0]},
        )


def downgrade() -> None:
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.drop_column("master_history")
