import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import ensure_sku_dirs, sku_dir
from img2ec.models import Project, SKU, SKUStatus, Variant
from img2ec.schemas.sku import SKUCreate, SKUDimensions, SKUOut
from img2ec.api.skus._helpers import _enrich

router = APIRouter()


@router.get("", response_model=list[SKUOut])
def list_skus(project_id: str, db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(SKU).filter_by(project_id=project_id).all()
    return [_enrich(s) for s in rows]


@router.post("", response_model=SKUOut, status_code=201)
def create_sku(project_id: str, payload: SKUCreate, db: Session = Depends(get_session)) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")
    # 同项目内 SKU 名称唯一（避免共享磁盘目录导致资产串）
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "SKU 名称不能为空")
    existing = db.query(SKU).filter_by(project_id=project_id, name=name).first()
    if existing:
        raise HTTPException(
            409,
            f"项目内已存在同名 SKU「{name}」(id={existing.id[:8]}…)。"
            f"请换个名字，或先删除老的。同名会共享磁盘目录导致老资产污染新 SKU。",
        )
    sku = SKU(id=str(uuid.uuid4()), project_id=project_id, name=name,
              scene_id=payload.scene_id, status=SKUStatus.DRAFT.value)
    db.add(sku)
    # 自动建默认变体；多色场景 Phase 4 加变体 CRUD
    db.add(Variant(
        id=str(uuid.uuid4()), product_id=sku.id, color_name="默认", status="draft",
    ))

    skud = sku_dir(Path(proj.root_path).parent, proj.name, payload.name, sku.id)
    ensure_sku_dirs(skud)

    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.get("/{sku_id}", response_model=SKUOut)
def get_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    return _enrich(sku)


@router.delete("/{sku_id}", status_code=204)
def delete_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> None:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    # 删 DB 前先记下磁盘路径，删 DB 后清盘上文件（避免同名 SKU 复活时捡到孤儿资产）
    proj = sku.project
    sku_path = None
    if proj is not None:
        try:
            sku_path = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
        except Exception:
            sku_path = None
    db.delete(sku)
    db.commit()
    if sku_path and sku_path.exists():
        import shutil
        try:
            shutil.rmtree(sku_path)
        except OSError:
            pass  # 文件没了不是错


class SkuPatchRequest(BaseModel):
    scene_id: str | None = None           # 传 string → 切换；不传 → 不改
    clear_scene: bool = False             # true → 把 scene_id 显式置 null（"不选任何模板"）
    name: str | None = None               # 改 SKU 名（同项目唯一；会重命名磁盘目录）


@router.patch("/{sku_id}", response_model=SKUOut)
def patch_sku(
    project_id: str, sku_id: str,
    payload: SkuPatchRequest,
    db: Session = Depends(get_session),
) -> dict:
    """更新 SKU 字段：name / scene_id / clear_scene。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")

    # 1) 改名 + 重命名磁盘目录 + DB 路径同步
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(400, "SKU 名称不能为空")
        if new_name != sku.name:
            existing = db.query(SKU).filter_by(project_id=project_id, name=new_name).first()
            if existing and existing.id != sku.id:
                raise HTTPException(409, f"项目内已存在同名 SKU「{new_name}」")
            proj = sku.project
            if proj:
                from img2ec.infra.fs_layout import slug as fs_slug
                root = Path(proj.root_path).parent
                old_dir = root / fs_slug(proj.name) / f"{fs_slug(sku.name)}-{sku.id[:8]}"
                new_dir = root / fs_slug(proj.name) / f"{fs_slug(new_name)}-{sku.id[:8]}"
                if old_dir.exists() and not new_dir.exists():
                    old_dir.rename(new_dir)
                old_str, new_str = str(old_dir), str(new_dir)

                def fix(s: str | None) -> str | None:
                    if not s: return s
                    if s.startswith(old_str + "/"): return new_str + s[len(old_str):]
                    if s == old_str: return new_str
                    return s

                for v in sku.variants:
                    if v.sku_thumb_path:
                        v.sku_thumb_path = fix(v.sku_thumb_path)
                    if v.sku_thumb_paths:
                        v.sku_thumb_paths = [fix(p) for p in v.sku_thumb_paths]
                    for im in v.images:
                        im.src_path = fix(im.src_path) or im.src_path
                        if im.master_paths:
                            im.master_paths = {k: fix(v) for k, v in im.master_paths.items()}
                        if im.master_history:
                            im.master_history = {k: [fix(p) for p in lst] for k, lst in im.master_history.items()}
                        if im.derived_paths:
                            im.derived_paths = {k: fix(v) for k, v in im.derived_paths.items()}
            sku.name = new_name

    # 2) 模板：scene_id 改 OR 显式清除
    if payload.clear_scene:
        sku.scene_id = None
    elif payload.scene_id is not None:
        from img2ec.models import Scene
        sc = db.get(Scene, payload.scene_id)
        if sc is None or sc.project_id != project_id:
            raise HTTPException(404, "scene not found in this project")
        sku.scene_id = payload.scene_id

    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.patch("/{sku_id}/dimensions", response_model=SKUOut)
def update_dimensions(
    project_id: str, sku_id: str,
    payload: SKUDimensions,
    db: Session = Depends(get_session),
) -> dict:
    """更新 SKU 物理尺寸（cm）。三项可分别为空。改尺寸后前端可单独触发 regenerate。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    sku.length_cm = payload.length_cm
    sku.width_cm = payload.width_cm
    sku.height_cm = payload.height_cm
    db.commit()
    db.refresh(sku)
    return _enrich(sku)
