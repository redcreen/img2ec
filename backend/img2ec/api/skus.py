import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from img2ec.config import get_settings
from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir, ensure_sku_dirs, source_dir
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus
from img2ec.schemas.sku import SKUCreate, SKUOut

router = APIRouter(prefix="/api/projects/{project_id}/skus", tags=["skus"])


def _path_to_url(path: str | None) -> str | None:
    """Convert an absolute filesystem path under root_path to a /static/projects/... URL."""
    if not path:
        return None
    root = str(get_settings().root_path)
    if path.startswith(root):
        rel = path[len(root):].lstrip("/")
        return f"/static/projects/{rel}"
    return None


def _enrich(sku: SKU) -> dict:
    """Serialize SKU + compute image URLs for web display."""
    out = SKUOut.model_validate(sku).model_dump()
    for img in out["images"]:
        img["src_url"] = _path_to_url(img.get("src_path"))
        img["master_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("master_paths") or {}).items()
        }
        img["derived_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("derived_paths") or {}).items()
        }
    return out


@router.get("", response_model=list[SKUOut])
def list_skus(project_id: str, db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(SKU).filter_by(project_id=project_id).all()
    return [_enrich(s) for s in rows]


@router.post("", response_model=SKUOut, status_code=201)
def create_sku(project_id: str, payload: SKUCreate, db: Session = Depends(get_session)) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")
    sku = SKU(id=str(uuid.uuid4()), project_id=project_id, name=payload.name,
              scene_id=payload.scene_id, status=SKUStatus.DRAFT.value)
    db.add(sku)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, payload.name)
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
    db.delete(sku)
    db.commit()


@router.post("/{sku_id}/images", response_model=SKUOut, status_code=201)
def upload_image(
    project_id: str, sku_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, project_id)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    src_d = source_dir(skud)
    src_d.mkdir(parents=True, exist_ok=True)
    dst = src_d / file.filename
    dst.write_bytes(file.file.read())

    img = SourceImage(
        id=str(uuid.uuid4()), sku_id=sku.id, name=file.filename, src_path=str(dst),
        status=ImageStatus.PENDING.value,
    )
    db.add(img)
    if sku.status == SKUStatus.DRAFT.value:
        sku.status = SKUStatus.READY.value
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.delete("/{sku_id}/images/{image_id}", status_code=204)
def delete_image(project_id: str, sku_id: str, image_id: str, db: Session = Depends(get_session)) -> None:
    img = db.get(SourceImage, image_id)
    if img is None or img.sku_id != sku_id:
        raise HTTPException(404, "image not found")
    if img.status not in (ImageStatus.PENDING.value, ImageStatus.FAILED.value):
        raise HTTPException(409, "cannot delete non-pending image")
    Path(img.src_path).unlink(missing_ok=True)
    db.delete(img)
    db.commit()


@router.post("/{sku_id}/process", status_code=202)
def process_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.scene_id is None:
        raise HTTPException(400, "no scene assigned")

    targets = [i for i in sku.images if i.status in (ImageStatus.PENDING.value, ImageStatus.FAILED.value)]
    if not targets:
        raise HTTPException(400, "no pending or failed images")

    # 重新开始处理时清掉 cancelled 标记
    sku.status = SKUStatus.RUNNING.value
    for img in targets:
        img.status = ImageStatus.PENDING.value
        img.err_msg = None
    db.commit()

    # 派发 Celery 任务
    from img2ec.tasks.pipeline_tasks import process_image_task
    for img in targets:
        process_image_task.delay(img.id)

    return {"queued": len(targets)}


@router.post("/{sku_id}/cancel", status_code=200)
def cancel_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    """请求停止处理。Pipeline 会在下一个 master 完成后检测到并 bail；已生成的 master 保留。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.status != SKUStatus.RUNNING.value:
        raise HTTPException(400, f"only running SKU can be cancelled (current: {sku.status})")
    sku.status = "cancelled"
    db.commit()
    return {"ok": True}
