"""variant.scene_id (per-variant template override)

Revision ID: c7f4d12e8a39
Revises: b6e02f78c40d
Create Date: 2026-05-15

加 variants.scene_id 列。回填规则：每个 variant.scene_id = 其父 sku.scene_id
（保持旧行为不变；之后 UI 改成 patch 变体而不是 SKU）。
"""
from alembic import op
import sqlalchemy as sa


revision = "c7f4d12e8a39"
down_revision = "b6e02f78c40d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("variants") as batch:
        batch.add_column(sa.Column("scene_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_variants_scene_id",
            "scenes",
            ["scene_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 回填：每个变体继承所属 SKU 当前的 scene_id
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE variants SET scene_id = ("
            "  SELECT skus.scene_id FROM skus WHERE skus.id = variants.product_id"
            ")"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("variants") as batch:
        batch.drop_constraint("fk_variants_scene_id", type_="foreignkey")
        batch.drop_column("scene_id")
