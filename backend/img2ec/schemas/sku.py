from datetime import datetime
from pydantic import BaseModel, Field


class SKUCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    scene_id: str | None = None


class SourceImageOut(BaseModel):
    id: str
    name: str
    src_path: str
    status: str
    progress: int
    err_msg: str | None
    master_paths: dict
    derived_paths: dict

    model_config = {"from_attributes": True}


class SKUOut(BaseModel):
    id: str
    project_id: str
    scene_id: str | None
    name: str
    status: str
    images: list[SourceImageOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
