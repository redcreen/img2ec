"""Variant (颜色变体) CRUD.

挂在 /api/projects/{project_id}/skus/{sku_id}/variants/* — 旧 SKU 路由前缀保留。
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir as sku_dir_fn, variant_dir as variant_dir_fn, slug
from img2ec.models import SKU, Variant


router = APIRouter(
    prefix="/api/projects/{project_id}/skus/{sku_id}/variants",
    tags=["variants"],
)


class VariantCreate(BaseModel):
    color_name: str = Field(..., min_length=1, max_length=60)


class VariantUpdate(BaseModel):
    color_name: str | None = Field(None, min_length=1, max_length=60)


class VariantThumbnail(BaseModel):
    """SKU 选图来源。image_keys 是有序列表（第一个 = 主色卡）。
    每个 key 形如 'img<idx>:<ratio>' 或 'size_white' / 'size_template'。
    支持单值字段 image_key 作为兼容（=单元素列表）。"""
    image_keys: list[str] | None = None
    image_key: str | None = None  # backward compat — single value


def _get_sku_or_404(db: Session, project_id: str, sku_id: str) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "product not found")
    return sku


def _ensure_color_unique(sku: SKU, color_name: str, exclude_id: str | None = None) -> None:
    for v in sku.variants:
        if v.id == exclude_id:
            continue
        if v.color_name == color_name:
            raise HTTPException(409, f"color '{color_name}' already exists on this product")


@router.post("", status_code=201)
def create_variant(
    project_id: str, sku_id: str,
    payload: VariantCreate,
    db: Session = Depends(get_session),
) -> dict:
    sku = _get_sku_or_404(db, project_id, sku_id)
    _ensure_color_unique(sku, payload.color_name.strip())

    v = Variant(
        id=str(uuid.uuid4()),
        product_id=sku.id,
        color_name=payload.color_name.strip(),
        status="draft",
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    # 准备目录结构（用 slug(color_name) 作为子目录）
    proj = sku.project
    if proj:
        skud = sku_dir_fn(Path(proj.root_path).parent, proj.name, sku.name)
        v_dir = skud / slug(payload.color_name.strip())
        for sub in ("source", "master", "outputs", "cutout"):
            (v_dir / sub).mkdir(parents=True, exist_ok=True)

    return {"id": v.id, "color_name": v.color_name, "status": v.status}


@router.patch("/{variant_id}")
def update_variant(
    project_id: str, sku_id: str, variant_id: str,
    payload: VariantUpdate,
    db: Session = Depends(get_session),
) -> dict:
    sku = _get_sku_or_404(db, project_id, sku_id)
    v = db.get(Variant, variant_id)
    if v is None or v.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    if payload.color_name:
        _ensure_color_unique(sku, payload.color_name.strip(), exclude_id=v.id)
        v.color_name = payload.color_name.strip()
    db.commit()
    db.refresh(v)
    return {"id": v.id, "color_name": v.color_name, "status": v.status}


def _resolve_image_key(v: Variant, key: str, sku) -> str:
    """Resolve image_key to absolute path. Raise HTTPException on failure."""
    if key.startswith("size_"):
        # 支持 size_<style> (=img0 兼容) 和 size_<style>_img<N>
        import re
        from img2ec.api.skus import _dimension_image_path_for_variant
        rest = key[len("size_"):]
        m = re.match(r"^(white|template)(?:_img(\d+))?$", rest)
        if not m:
            raise HTTPException(400, f"invalid size key: {key}")
        style = m.group(1)
        idx = int(m.group(2)) if m.group(2) is not None else 0
        if not v.images:
            raise HTTPException(400, "variant has no source images")
        if idx >= len(v.images):
            raise HTTPException(400, f"image index {idx} out of range")
        p = _dimension_image_path_for_variant(v, style, idx)
        if p is None or not p.exists():
            raise HTTPException(400, f"dimension diagram {style}_img{idx} not generated yet")
        return str(p)
    if key.startswith("img"):
        try:
            idx_part, ratio = key[3:].split(":", 1)
            idx = int(idx_part)
        except (ValueError, IndexError):
            raise HTTPException(400, f"invalid image_key: {key}")
        if idx < 0 or idx >= len(v.images):
            raise HTTPException(400, f"image index {idx} out of range")
        masters = v.images[idx].master_paths or {}
        if ratio not in masters:
            raise HTTPException(400, f"variant image {idx} has no {ratio} master")
        return masters[ratio]
    raise HTTPException(400, f"invalid image_key format: {key}")


@router.post("/{variant_id}/thumbnail")
def set_variant_thumbnail(
    project_id: str, sku_id: str, variant_id: str,
    payload: VariantThumbnail,
    db: Session = Depends(get_session),
) -> dict:
    """Set 该变体的 SKU 色卡列表（多候选，list[0] 为主色卡）。
    传 image_keys=[] 或 image_key=None 清空。
    """
    sku = _get_sku_or_404(db, project_id, sku_id)
    v = db.get(Variant, variant_id)
    if v is None or v.product_id != sku.id:
        raise HTTPException(404, "variant not found")

    # 统一为 keys 列表
    if payload.image_keys is not None:
        keys = payload.image_keys
    elif payload.image_key is not None:
        keys = [payload.image_key]
    else:
        keys = []

    paths: list[str] = [_resolve_image_key(v, k, sku) for k in keys]
    v.sku_thumb_paths = paths
    v.sku_thumb_path = paths[0] if paths else None
    db.commit()
    db.refresh(v)
    return {"id": v.id, "sku_thumb_paths": v.sku_thumb_paths, "sku_thumb_path": v.sku_thumb_path}


@router.delete("/{variant_id}", status_code=204)
def delete_variant(
    project_id: str, sku_id: str, variant_id: str,
    db: Session = Depends(get_session),
) -> None:
    sku = _get_sku_or_404(db, project_id, sku_id)
    if len(sku.variants) <= 1:
        raise HTTPException(400, "cannot delete the only variant of a product")
    v = db.get(Variant, variant_id)
    if v is None or v.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    db.delete(v)
    db.commit()
