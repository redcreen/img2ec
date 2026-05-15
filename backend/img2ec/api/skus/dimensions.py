from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import SKU
from img2ec.schemas.sku import SKUOut
from img2ec.api.skus._helpers import DIMENSION_STYLES, _dimension_image_path_for_variant, _enrich, _get_variant_or_default

router = APIRouter()

class DimensionDeleteRequest(BaseModel):
    variant_id: str
    style: str  # white | template
    image_idx: int


@router.post("/{sku_id}/dimension/delete-all", response_model=SKUOut)
def delete_all_dimension(
    project_id: str, sku_id: str,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """删除该变体（缺省 default）下所有尺寸图文件 + Redis 状态。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    variant = _get_variant_or_default(sku, variant_id)
    if variant is None:
        raise HTTPException(404, "variant not found")

    from img2ec.infra import state_store
    for style in DIMENSION_STYLES:
        for i in range(len(variant.images)):
            p = _dimension_image_path_for_variant(variant, style, i)
            if p and p.exists():
                try: p.unlink()
                except OSError: pass
            state_store.dim_clear(variant.id, f"{style}_img{i}")

    db.refresh(sku)
    return _enrich(sku)


@router.post("/{sku_id}/dimension/delete", status_code=200)
def delete_dimension_image(
    project_id: str, sku_id: str,
    payload: DimensionDeleteRequest,
    db: Session = Depends(get_session),
) -> dict:
    """删除某张尺寸图（单张 = style × image_idx）。物理文件 + 状态都清。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    variant = next((v for v in sku.variants if v.id == payload.variant_id), None)
    if variant is None:
        raise HTTPException(404, "variant not found")
    if payload.style not in DIMENSION_STYLES:
        raise HTTPException(400, f"invalid style {payload.style}")
    if payload.image_idx < 0 or payload.image_idx >= len(variant.images):
        raise HTTPException(400, "image_idx out of range")

    p = _dimension_image_path_for_variant(variant, payload.style, payload.image_idx)
    if p is not None and p.exists():
        try:
            p.unlink()
        except OSError as e:
            raise HTTPException(500, f"failed to delete file: {e}")

    # 清状态
    from img2ec.infra import state_store
    state_store.dim_clear(variant.id, f"{payload.style}_img{payload.image_idx}")

    db.refresh(sku)
    return _enrich(sku)


class DimensionRegenerateRequest(BaseModel):
    styles: list[str] = ["white"]  # subset of {"white","template"}
    image_indices: list[int] | None = None  # 哪些原图（按 variant.images 索引）；None=只用第 0 张


@router.post("/{sku_id}/dimension/regenerate", response_model=SKUOut, status_code=202)
def regenerate_dimension_diagram(
    project_id: str, sku_id: str,
    payload: DimensionRegenerateRequest | None = None,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """异步为指定变体（缺省 default）生成尺寸图。"""
    from img2ec.models import Scene

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.length_cm is None or sku.width_cm is None or sku.height_cm is None:
        raise HTTPException(400, "all three dimensions (length/width/height) must be set")

    variant = _get_variant_or_default(sku, variant_id)
    if variant is None or not variant.images:
        raise HTTPException(400, "variant has no source images")

    requested = (payload.styles if payload else None) or ["white"]
    invalid = [s for s in requested if s not in DIMENSION_STYLES]
    if invalid:
        raise HTTPException(400, f"invalid styles: {invalid}; allowed: {list(DIMENSION_STYLES)}")
    if not requested:
        raise HTTPException(400, "styles cannot be empty")

    indices = (payload.image_indices if payload and payload.image_indices is not None else [0])
    bad_idx = [i for i in indices if i < 0 or i >= len(variant.images)]
    if bad_idx:
        raise HTTPException(400, f"image_indices out of range: {bad_idx}")
    if not indices:
        raise HTTPException(400, "image_indices cannot be empty")

    effective_scene_id = variant.scene_id or sku.scene_id
    scene = db.get(Scene, effective_scene_id) if effective_scene_id else None
    if "template" in requested and (scene is None or not scene.prompt):
        raise HTTPException(400, "template style requires a scene template on the variant or SKU")

    # (style, idx) 组合 — 状态通过 Redis 跨进程共享
    from img2ec.infra import state_store
    combos = [(s, i) for s in requested for i in indices]
    existing = state_store.dim_get_all(variant.id)
    busy_combos = [f"{s}_img{i}" for s, i in combos if existing.get(f"{s}_img{i}", {}).get("status") == "generating"]
    if busy_combos:
        raise HTTPException(409, f"already generating: {busy_combos}")

    # 标记 generating + 立即派工到 celery worker
    from img2ec.tasks.dim_tasks import regenerate_dimension_task
    for s, i in combos:
        state_store.dim_set(variant.id, f"{s}_img{i}", "generating")
        regenerate_dimension_task.delay(sku.id, variant.id, s, i)

    db.refresh(sku)
    return _enrich(sku)
