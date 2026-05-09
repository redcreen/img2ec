from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    desc: Mapped[str] = mapped_column(String(500), default="")
    root_path: Mapped[str] = mapped_column(String(500), nullable=False)

    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
    skus = relationship("SKU", back_populates="project", cascade="all, delete-orphan")
