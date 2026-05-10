from enum import Enum

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class Platform(str, Enum):
    DOUYIN = "douyin"
    SHIPINHAO = "shipinhao"
    XIAOHONGSHU = "xiaohongshu"


class PlatformOutputCopy(Base, TimestampMixin):
    __tablename__ = "platform_output_copies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="")
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    selling_points: Mapped[list] = mapped_column(JSON, default=list)
    description_md: Mapped[str] = mapped_column(Text, default="")
    category_path: Mapped[str] = mapped_column(String(200), default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)  # 全量原始响应留 debug

    sku = relationship("SKU")
