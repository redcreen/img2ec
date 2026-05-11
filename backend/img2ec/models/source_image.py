from enum import Enum
from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class ImageStatus(str, Enum):
    PENDING = "pending"
    CUTTING = "cutting"
    GENERATING = "generating"
    COMPOSING = "composing"
    DONE = "done"
    FAILED = "failed"


class SourceImage(Base, TimestampMixin):
    __tablename__ = "source_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # variant_id 指向具体颜色变体；老数据迁移时挂到产品默认变体
    variant_id: Mapped[str] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    src_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ImageStatus.PENDING.value, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    master_paths: Mapped[dict] = mapped_column(JSON, default=dict)
    derived_paths: Mapped[dict] = mapped_column(JSON, default=dict)

    variant = relationship("Variant", back_populates="images")

    # 兼容属性：旧代码依赖 img.sku_id / img.sku — 经 variant 转发到 product
    @property
    def sku_id(self) -> str:
        return self.variant.product_id if self.variant else ""

    @property
    def sku(self):
        return self.variant.product if self.variant else None
