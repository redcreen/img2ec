"""variant-level platform_output_copies + cleanup SKU-level detail-template.jpg

Revision ID: a8c93e1d2f15
Revises: f4a91b2c7e83
Create Date: 2026-05-14 21:50:00.000000

文案 + 详情页全部按 variant 维度独立维护。
- 表 platform_output_copies：sku_id 改为 variant_id，加唯一约束 (variant_id, platform)
- 既有行全部丢弃（文案是 Codex 重新生成的，没有"迁移到默认变体"的语义）
- 文件清理：删掉所有 outputs/<platform>/detail-template.jpg（SKU 级旧位置）
  新位置 outputs/<platform>/<variant_slug>/detail-template.jpg 由代码按变体写入
"""
import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8c93e1d2f15"
down_revision: Union[str, Sequence[str], None] = "f4a91b2c7e83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cleanup_sku_level_detail_files() -> None:
    """删除所有旧的 SKU 级 outputs/<platform>/detail-template.jpg 文件。
    新代码只会读变体级路径，不会留尾巴。"""
    root_env = os.environ.get("IMG2EC_ROOT_PATH")
    root = Path(root_env) if root_env else Path.home() / "img2ec" / "projects"
    if not root.exists():
        return
    deleted = 0
    for project_dir in root.iterdir():
        if not project_dir.is_dir():
            continue
        for sku_dir in project_dir.iterdir():
            outputs = sku_dir / "outputs"
            if not outputs.is_dir():
                continue
            for plat_dir in outputs.iterdir():
                # SKU 级旧文件就在 plat_dir 直接下面
                old = plat_dir / "detail-template.jpg"
                if old.is_file():
                    try:
                        old.unlink()
                        deleted += 1
                    except OSError:
                        pass
    if deleted:
        print(f"[a8c93e1d2f15] cleaned {deleted} legacy SKU-level detail-template.jpg files")


def upgrade() -> None:
    # 既有行丢弃 —— 旧 sku_id 没办法无歧义映射到某个 variant
    op.execute("DELETE FROM platform_output_copies")

    with op.batch_alter_table("platform_output_copies", recreate="always") as batch:
        batch.drop_column("sku_id")
        batch.add_column(sa.Column("variant_id", sa.String(length=36), nullable=False))
        batch.create_foreign_key(
            "fk_copy_variant", "variants", ["variant_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_unique_constraint(
            "uq_copy_variant_platform", ["variant_id", "platform"],
        )

    _cleanup_sku_level_detail_files()


def downgrade() -> None:
    op.execute("DELETE FROM platform_output_copies")
    with op.batch_alter_table("platform_output_copies", recreate="always") as batch:
        batch.drop_constraint("uq_copy_variant_platform", type_="unique")
        batch.drop_constraint("fk_copy_variant", type_="foreignkey")
        batch.drop_column("variant_id")
        batch.add_column(sa.Column("sku_id", sa.String(length=36), nullable=False))
        batch.create_foreign_key(
            "fk_copy_sku", "skus", ["sku_id"], ["id"], ondelete="CASCADE",
        )
