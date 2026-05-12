from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


# 节庆闭集：限定 8 个值，便于筛选与下游 prompt 增强
FESTIVALS = (
    "通用", "春节", "元宵", "端午", "七夕", "中秋", "重阳", "腊八",
)

# 创建来源：system=随项目默认；user=用户手工；ai_keywords=AI 关键词扩展；ai_reference=AI 图反推
CREATED_BY_VALUES = ("system", "user", "ai_keywords", "ai_reference")


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="自定义")
    desc: Mapped[str] = mapped_column(String(500), default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    ref_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_adapter_weight: Mapped[int] = mapped_column(Integer, default=60)
    base_model: Mapped[str] = mapped_column(String(60), default="flux-dev-fp8")
    # 节庆 tag（闭集中的某一项）+ 创建来源
    festival: Mapped[str] = mapped_column(String(20), default="通用", nullable=False)
    created_by: Mapped[str] = mapped_column(String(20), default="user", nullable=False)

    project = relationship("Project", back_populates="scenes")
