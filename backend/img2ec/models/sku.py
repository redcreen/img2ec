from enum import Enum
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class SKUStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class SKU(Base, TimestampMixin):
    """电商语义里的"产品" / SPU；老的"SKU"概念升级为 Product。表名仍是 skus（Phase 5 再改）。

    一个 Product 包含 1 至多个 Variant（颜色变体）。文案 / 模板 / 物理尺寸跨变体共享，
    源素材 + 输出图按变体隔离。
    """

    __tablename__ = "skus"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SKUStatus.DRAFT.value, nullable=False)

    # 产品物理尺寸（cm，可选）。变体间共享。
    length_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)

    project = relationship("Project", back_populates="skus")
    scene = relationship("Scene")
    variants = relationship(
        "Variant", back_populates="product", cascade="all, delete-orphan",
        order_by="Variant.created_at",
    )

    # 兼容旧代码：sku.images 聚合所有变体的图
    @property
    def images(self):
        out = []
        for v in self.variants:
            out.extend(v.images)
        return out

    @property
    def default_variant(self):
        """返回第一个变体（默认 "默认色"）。所有产品至少有 1 个变体，由 create_sku 保证。"""
        return self.variants[0] if self.variants else None
