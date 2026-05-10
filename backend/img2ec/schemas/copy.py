from datetime import datetime
from pydantic import BaseModel


class CopyOut(BaseModel):
    id: str
    platform: str
    title: str
    subtitle: str
    selling_points: list[str]
    description_md: str
    category_path: str
    keywords: list[str]
    hashtags: list[str]
    video_script: str = ""
    detail_template_url: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
