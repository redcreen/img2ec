from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    desc: str = ""
    copy_default_scenes: bool = True


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    desc: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    desc: str
    root_path: str
    sku_count: int
    scene_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
