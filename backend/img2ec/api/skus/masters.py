from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import SKU
from img2ec.schemas.sku import SKUOut
from img2ec.api.skus._helpers import _enrich

router = APIRouter()

class DeleteMasterVersionRequest(BaseModel):
    image_id: str
    ratio: str
    path: str  # 绝对路径（前端从 master_history_urls 取的 path 字段回传）


@router.post("/{sku_id}/master-versions/delete", status_code=200)
def delete_master_version(
    project_id: str, sku_id: str,
    payload: DeleteMasterVersionRequest,
    db: Session = Depends(get_session),
) -> dict:
    """删除某张 master 图的一个版本。如删的是 primary，下一个版本自动升 primary。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")

    from img2ec.models import SourceImage
    img = db.get(SourceImage, payload.image_id)
    if img is None:
        raise HTTPException(404, "image not found")

    hist = {k: list(v) for k, v in (img.master_history or {}).items()}
    # 兜底：旧数据没 history 但 master_paths 里有
    mp = dict(img.master_paths or {})
    if payload.ratio not in hist and payload.ratio in mp:
        hist[payload.ratio] = [mp[payload.ratio]]

    versions = hist.get(payload.ratio, [])
    if payload.path not in versions:
        raise HTTPException(404, "version not found for this ratio")

    versions = [p for p in versions if p != payload.path]
    # 物理文件
    try:
        Path(payload.path).unlink()
    except FileNotFoundError:
        pass

    if versions:
        hist[payload.ratio] = versions
        mp[payload.ratio] = versions[0]  # primary = newest 余下
    else:
        hist.pop(payload.ratio, None)
        mp.pop(payload.ratio, None)
        # 派生图按 ratio 找不到 primary 后无法更新，留旧的（用户可重生）

    img.master_history = hist
    img.master_paths = mp
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.post("/{sku_id}/images/{image_id}/delete-all-masters", response_model=SKUOut)
def delete_all_masters_for_image(
    project_id: str, sku_id: str, image_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """删除该原图下所有 master 版本（含历史 + primary）。物理文件 + DB 一并清。"""
    from img2ec.models import SourceImage
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    img = db.get(SourceImage, image_id)
    if img is None:
        raise HTTPException(404, "image not found")

    # 收集所有要删的路径（master_history 优先，fallback 到 master_paths）
    all_paths: set[str] = set()
    for k, lst in (img.master_history or {}).items():
        for p in lst:
            if p: all_paths.add(p)
    for k, p in (img.master_paths or {}).items():
        if p: all_paths.add(p)
    for p in all_paths:
        try: Path(p).unlink()
        except FileNotFoundError: pass
        except OSError: pass

    img.master_history = {}
    img.master_paths = {}
    # 派生图也清（基于已删的 master）
    img.derived_paths = {}
    db.commit()
    db.refresh(sku)
    return _enrich(sku)
