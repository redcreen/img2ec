from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import slug as fs_slug
from img2ec.models import PlatformOutputCopy, Project, SKU, Variant
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
    from img2ec.infra import state_store
    variant = _get_variant_or_404(db, project_id, sku_id, variant_id)
    rows = db.query(PlatformOutputCopy).filter_by(variant_id=variant.id).all()
    regenerating = state_store.copy_regen_get(variant.id)
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
            regenerating=regenerating,
        )
        for row in rows
    ]


@router.post("/regenerate", status_code=202)
def regenerate(
    project_id: str, sku_id: str, variant_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """触发文案 + 详情页拼图异步重生成。
    Codex LLM 调用 1-3 分钟，做成 fire-and-forget。前端轮询 GET /copy 看
    copy.regenerating；标志在 worker 完成时清掉。
    """
    from img2ec.infra import state_store

    variant = _get_variant_or_404(db, project_id, sku_id, variant_id)
    if not variant.images:
        raise HTTPException(400, "variant has no source images")
    ref_img = next(
        (im for im in variant.images
         if im.master_paths and im.master_paths.get("1x1")),
        None,
    )
    if ref_img is None:
        raise HTTPException(400, "no master 1x1 yet — process at least one image first")
    if state_store.copy_regen_get(variant.id):
        return {"queued": True, "already_running": True}

    state_store.copy_regen_set(variant.id)
    from img2ec.tasks.copy_tasks import regenerate_copy_task
    regenerate_copy_task.delay(project_id, sku_id, variant_id)
    return {"queued": True, "variant_id": variant_id}
