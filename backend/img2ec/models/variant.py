"""Variant (颜色变体) — 电商语义的 SKU。一个 Product（旧 SKU）下可挂多个 Variant。

每个 Variant 持有自己的 source_images + 输出图 + 模板（scene_id）。物理尺寸在 Product 级共享。
"""
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class Variant(Base, TimestampMixin):
    __tablename__ = "variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("skus.id", ondelete="CASCADE"), nullable=False,
    )
    color_name: Mapped[str] = mapped_column(String(60), default="默认", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # 每个变体可独立指定模板；NULL = 走 SKU 默认 scene_id（向后兼容）
    scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True,
    )
    # 单值色卡（旧字段，仍读取以兼容；新代码用 sku_thumb_paths 列表）
    sku_thumb_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 多候选色卡（有序列表；list[0] = 主色卡）
    sku_thumb_paths: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    product = relationship("SKU", back_populates="variants")
    scene = relationship("Scene")
    images = relationship(
        "SourceImage", back_populates="variant", cascade="all, delete-orphan",
        order_by="SourceImage.order_index",
    )

    @property
    def effective_scene_id(self) -> str | None:
        """模板解析：变体自带 > SKU 默认。每张图可再覆盖（见 pipeline）。"""
        return self.scene_id or (self.product.scene_id if self.product else None)

    @property
    def primary_thumb_path(self) -> str | None:
        """主色卡：列表第一项；列表空时退回旧的单值字段。"""
        if self.sku_thumb_paths:
            return self.sku_thumb_paths[0]
        return self.sku_thumb_path
