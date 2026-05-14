from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.core.copy_gen import generate_copy_for_sku
from img2ec.db import get_session
from img2ec.infra.fs_layout import slug as fs_slug
from img2ec.infra.llm_provider import CodexCLIProvider, LLMProviderError
from img2ec.models import PlatformOutputCopy, Project, Scene, SKU, Variant
from img2ec.schemas.copy import CopyOut

router = APIRouter(
    prefix="/api/projects/{project_id}/skus/{sku_id}/variants/{variant_id}/copy",
    tags=["copy"],
)


def _get_variant_or_404(db: Session, project_id: str, sku_id: str, variant_id: str) -> Variant:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    v = db.get(Variant, variant_id)
    if v is None or v.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    return v


def _detail_template_url(db: Session, variant: Variant, platform: str) -> str | None:
    """该变体在该平台的详情页 URL。
    带 ?t=<mtime> 防止浏览器缓存（compose 重渲后 URL 不变但文件已变）。"""
    from img2ec.config import get_settings

    sku = variant.product
    proj = db.get(Project, sku.project_id) if sku else None
    if not (sku and proj):
        return None
    sku_dirname = f"{fs_slug(sku.name)}-{sku.id[:8]}"
    variant_dirname = fs_slug(variant.color_name)
    base = (
        f"/static/projects/{fs_slug(proj.name)}/{sku_dirname}/outputs/"
        f"{platform}/{variant_dirname}/detail-template.jpg"
    )
    file_path = (
        get_settings().root_path
        / fs_slug(proj.name)
        / sku_dirname
        / "outputs"
        / platform
        / variant_dirname
        / "detail-template.jpg"
    )
    try:
        if file_path.exists():
            return f"{base}?t={int(file_path.stat().st_mtime)}"
    except OSError:
        pass
    return base


@router.get("", response_model=list[CopyOut])
def list_copy(
    project_id: str, sku_id: str, variant_id: str,
    db: Session = Depends(get_session),
) -> list[CopyOut]:
    variant = _get_variant_or_404(db, project_id, sku_id, variant_id)
    rows = db.query(PlatformOutputCopy).filter_by(variant_id=variant.id).all()
    return [
        CopyOut(
            id=row.id, platform=row.platform,
            title=row.title, subtitle=row.subtitle,
            selling_points=row.selling_points,
            description_md=row.description_md,
            category_path=row.category_path,
            keywords=row.keywords, hashtags=row.hashtags,
            video_script=row.video_script,
            created_at=row.created_at, updated_at=row.updated_at,
            detail_template_url=_detail_template_url(db, variant, row.platform),
        )
        for row in rows
    ]


@router.post("/regenerate", response_model=list[CopyOut], status_code=201)
def regenerate(
    project_id: str, sku_id: str, variant_id: str,
    db: Session = Depends(get_session),
) -> list[CopyOut]:
    variant = _get_variant_or_404(db, project_id, sku_id, variant_id)
    images = list(variant.images)
    if not images:
        raise HTTPException(400, "variant has no source images")
    master = images[0].master_paths.get("1x1") if images[0].master_paths else None
    if not master:
        raise HTTPException(400, "no master image to use as reference")

    sku = variant.product
    scene = db.get(Scene, sku.scene_id) if sku.scene_id else None

    # 该变体下旧行全部丢弃，重新生成
    db.query(PlatformOutputCopy).filter_by(variant_id=variant.id).delete()

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

    from img2ec.tasks.pipeline_tasks import _persist_copy
    _persist_copy(db, variant.id, result)

    return list_copy(project_id, sku_id, variant_id, db)
