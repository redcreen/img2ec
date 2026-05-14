from enum import Enum

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class Platform(str, Enum):
    DOUYIN = "douyin"
    SHIPINHAO = "shipinhao"
    XIAOHONGSHU = "xiaohongshu"


class PlatformOutputCopy(Base, TimestampMixin):
    """每个 Variant + Platform 一行。文案 + 详情页都按颜色独立维护。"""

    __tablename__ = "platform_output_copies"
    __table_args__ = (
        UniqueConstraint("variant_id", "platform", name="uq_copy_variant_platform"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    variant_id: Mapped[str] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="")
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    selling_points: Mapped[list] = mapped_column(JSON, default=list)
    description_md: Mapped[str] = mapped_column(Text, default="")
    category_path: Mapped[str] = mapped_column(String(200), default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    video_script: Mapped[str] = mapped_column(Text, default="")
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)

    variant = relationship("Variant")
