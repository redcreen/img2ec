"""scene.festival + scene.created_by

Revision ID: e2f8b9d04c12
Revises: d8e5c2a13f47
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f8b9d04c12"
down_revision: Union[str, Sequence[str], None] = "d8e5c2a13f47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scenes") as batch_op:
        batch_op.add_column(
            sa.Column("festival", sa.String(length=20), nullable=False, server_default="通用")
        )
        batch_op.add_column(
            sa.Column("created_by", sa.String(length=20), nullable=False, server_default="user")
        )

    # 现存 system 默认场景（DEFAULT_SCENES 复制过来的）打 system 标
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE scenes SET created_by='system' WHERE name IN ('纯白底', '中式实木桌面·窗光')"
    ))


def downgrade() -> None:
    with op.batch_alter_table("scenes") as batch_op:
        batch_op.drop_column("created_by")
        batch_op.drop_column("festival")
