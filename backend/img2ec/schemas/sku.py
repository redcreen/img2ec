from datetime import datetime
from pydantic import BaseModel, Field


class SKUCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    scene_id: str | None = None


class SKUDimensions(BaseModel):
    length_cm: float | None = Field(None, gt=0, le=10000)
    width_cm: float | None = Field(None, gt=0, le=10000)
    height_cm: float | None = Field(None, gt=0, le=10000)


class SourceImageOut(BaseModel):
    id: str
    name: str
    src_path: str
    status: str
    progress: int
    err_msg: str | None
    master_paths: dict
    derived_paths: dict
    # Web-servable URLs (computed from absolute filesystem paths in skus.py routes)
    src_url: str | None = None
    master_urls: dict = Field(default_factory=dict)
    derived_urls: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class VariantOut(BaseModel):
    id: str
    color_name: str
    status: str
    # 主色卡（兼容字段，list[0]）
    sku_thumb_path: str | None = None
    sku_thumb_url: str | None = None
    # 多候选色卡（有序）
    sku_thumb_paths: list[str] = Field(default_factory=list)
    sku_thumb_urls: list[str] = Field(default_factory=list)
    images: list[SourceImageOut] = Field(default_factory=list)
    # 尺寸图 per-variant
    dimension_urls: dict[str, str] = Field(default_factory=dict)
    dimension_states: dict[str, dict] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SKUOut(BaseModel):
    id: str
    project_id: str
    scene_id: str | None
    name: str
    status: str
    # 产品级（跨变体共享）
    length_cm: float | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    # 变体列表
    variants: list[VariantOut] = Field(default_factory=list)
    # 兼容字段（聚合所有变体的图片）
    images: list[SourceImageOut] = Field(default_factory=list)
    # 兼容字段（向后兼容：未传 variant 时取 default variant 的）
    dimension_urls: dict[str, str] = Field(default_factory=dict)
    dimension_states: dict[str, dict] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
