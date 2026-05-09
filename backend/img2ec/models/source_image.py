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
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    src_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ImageStatus.PENDING.value, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    master_paths: Mapped[dict] = mapped_column(JSON, default=dict)
    derived_paths: Mapped[dict] = mapped_column(JSON, default=dict)

    sku = relationship("SKU", back_populates="images")
