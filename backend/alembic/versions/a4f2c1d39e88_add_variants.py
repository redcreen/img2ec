"""add variants table; migrate source_images.sku_id → variant_id

Each existing SKU gets one auto-created "默认" variant; all its source_images
are reassigned to that variant. File paths on disk are NOT moved — they stay
where they are (default variant uses the legacy path layout).

Revision ID: a4f2c1d39e88
Revises: c91e2f4a8d77
Create Date: 2026-05-11 12:00:00
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4f2c1d39e88"
down_revision: Union[str, Sequence[str], None] = "c91e2f4a8d77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. variants 表
    op.create_table(
        "variants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36),
                  sa.ForeignKey("skus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("color_name", sa.String(60), nullable=False, server_default="默认"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("sku_thumb_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # 2. source_images 加 variant_id（暂 nullable，填完后再 NOT NULL）
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.add_column(sa.Column("variant_id", sa.String(36), nullable=True))

    # 3. 老数据：每个 SKU 建一个"默认"变体 + 把 source_images 挂上去
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, status FROM skus")).fetchall()
    for sku_id, sku_status in rows:
        vid = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO variants (id, product_id, color_name, status, "
                "created_at, updated_at) VALUES (:vid, :pid, :color, :status, "
                "datetime('now'), datetime('now'))"
            ),
            {"vid": vid, "pid": sku_id, "color": "默认", "status": sku_status or "draft"},
        )
        bind.execute(
            sa.text("UPDATE source_images SET variant_id = :vid WHERE sku_id = :sid"),
            {"vid": vid, "sid": sku_id},
        )

    # 4. source_images 把 variant_id 改 NOT NULL，丢掉 sku_id 列
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.alter_column("variant_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_source_images_variant", "variants",
            ["variant_id"], ["id"], ondelete="CASCADE",
        )
        # SQLite 在 batch_alter 里 drop_column 用 reflect 方式做，安全
        batch_op.drop_column("sku_id")


def downgrade() -> None:
    # 反向：先加回 sku_id（nullable），从 variant 回填 product_id，删 variants
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.add_column(sa.Column("sku_id", sa.String(36), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE source_images "
        "SET sku_id = (SELECT product_id FROM variants WHERE variants.id = source_images.variant_id)"
    ))

    with op.batch_alter_table("source_images") as batch_op:
        batch_op.alter_column("sku_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_source_images_sku", "skus",
            ["sku_id"], ["id"], ondelete="CASCADE",
        )
        batch_op.drop_constraint("fk_source_images_variant", type_="foreignkey")
        batch_op.drop_column("variant_id")

    op.drop_table("variants")
