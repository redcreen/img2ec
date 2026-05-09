from datetime import datetime
from pydantic import BaseModel, Field


class SceneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str = "自定义"
    desc: str = ""
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = ""
    ip_adapter_weight: int = Field(60, ge=0, le=100)
    base_model: str = "flux-dev-fp8"


class SceneOut(BaseModel):
    id: str
    project_id: str
    name: str
    category: str
    desc: str
    prompt: str
    negative_prompt: str
    ip_adapter_weight: int
    base_model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
