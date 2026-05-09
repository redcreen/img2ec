from enum import Enum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class SKUStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class SKU(Base, TimestampMixin):
    __tablename__ = "skus"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SKUStatus.DRAFT.value, nullable=False)

    project = relationship("Project", back_populates="skus")
    scene = relationship("Scene")
    images = relationship("SourceImage", back_populates="sku", cascade="all, delete-orphan")
