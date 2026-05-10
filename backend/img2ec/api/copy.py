import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.core.copy_gen import generate_copy_for_sku
from img2ec.db import get_session
from img2ec.infra.fs_layout import slug as fs_slug
from img2ec.infra.llm_provider import CodexCLIProvider, LLMProviderError
from img2ec.models import PlatformOutputCopy, Project, Scene, SKU, SKUStatus
from img2ec.schemas.copy import CopyOut

router = APIRouter(prefix="/api/skus/{sku_id}/copy", tags=["copy"])


def _detail_template_url(db: Session, sku_id: str, platform: str) -> str | None:
    """Compute the detail template URL if the file exists.

    Path: /static/projects/<project_slug>/<sku_slug>/outputs/<platform>/<image_stem>-detail-template.jpg
    """
    sku = db.get(SKU, sku_id)
    proj = db.get(Project, sku.project_id) if sku else None
    if not (sku and proj and sku.images):
        return None
    image_stem = Path(sku.images[0].name).stem
    return f"/static/projects/{fs_slug(proj.name)}/{fs_slug(sku.name)}/outputs/{platform}/{image_stem}-detail-template.jpg"


@router.get("", response_model=list[CopyOut])
def list_copy(sku_id: str, db: Session = Depends(get_session)) -> list[CopyOut]:
    rows = db.query(PlatformOutputCopy).filter_by(sku_id=sku_id).all()
    result = []
    for row in rows:
        # Convert ORM to dict, then add computed detail_template_url
        data = {
            "id": row.id,
            "platform": row.platform,
            "title": row.title,
            "subtitle": row.subtitle,
            "selling_points": row.selling_points,
            "description_md": row.description_md,
            "category_path": row.category_path,
            "keywords": row.keywords,
            "hashtags": row.hashtags,
            "video_script": row.video_script,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "detail_template_url": _detail_template_url(db, sku_id, row.platform),
        }
        result.append(CopyOut(**data))
    return result


@router.post("/regenerate", response_model=list[CopyOut], status_code=201)
def regenerate(sku_id: str, db: Session = Depends(get_session)) -> list[CopyOut]:
    sku = db.get(SKU, sku_id)
    if sku is None:
        raise HTTPException(404, "sku not found")
    if sku.status != SKUStatus.DONE.value:
        raise HTTPException(400, "SKU must be done before generating copy")

    images = sku.images
    if not images:
        raise HTTPException(400, "no images on SKU")
    master = images[0].master_paths.get("1x1") if images[0].master_paths else None
    if not master:
        raise HTTPException(400, "no master image to use as reference")

    scene = db.get(Scene, sku.scene_id) if sku.scene_id else None

    # Wipe existing
    db.query(PlatformOutputCopy).filter_by(sku_id=sku_id).delete()

    try:
        result = generate_copy_for_sku(
            provider=CodexCLIProvider(),
            image_path=Path(master),
            sku_name=sku.name,
            scene_name=scene.name if scene else "",
            scene_category=scene.category if scene else "",
        )
    except LLMProviderError as e:
        raise HTTPException(502, f"LLM error: {e}")

    # Persist (same logic as pipeline_tasks._persist_copy)
    from img2ec.tasks.pipeline_tasks import _persist_copy
    _persist_copy(db, sku_id, result)

    return list_copy(sku_id, db)
