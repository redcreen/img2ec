import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus, Variant
from img2ec.schemas.sku import SKUOut
from img2ec.api.skus._helpers import _enrich, _get_variant_or_default

router = APIRouter()


@router.post("/{sku_id}/images", response_model=SKUOut, status_code=201)
def upload_image(
    project_id: str, sku_id: str,
    file: UploadFile = File(...),
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, project_id)

    variant = _get_variant_or_default(sku, variant_id)
    if variant is None:
        variant = Variant(
            id=str(uuid.uuid4()), product_id=sku.id, color_name="默认", status="draft",
        )
        db.add(variant)
        db.flush()

    from img2ec.infra.fs_layout import variant_dir as variant_dir_fn
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
    vdir = variant_dir_fn(skud, variant)
    src_d = vdir / "source"
    src_d.mkdir(parents=True, exist_ok=True)

    orig_name = file.filename or "upload"
    raw_bytes = file.file.read()
    # HEIC 自动转 JPG — Codex 拒绝 heic 输入；同时让前端 <img> 也能直显
    final_name = orig_name
    if orig_name.lower().endswith((".heic", ".heif")):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            from PIL import Image
            import io
            with Image.open(io.BytesIO(raw_bytes)) as im:
                rgb = im.convert("RGB")
                buf = io.BytesIO()
                rgb.save(buf, "JPEG", quality=92)
                raw_bytes = buf.getvalue()
            final_name = Path(orig_name).with_suffix(".jpg").name
        except Exception as e:
            raise HTTPException(400, f"HEIC 解码失败：{e}")
    dst = src_d / final_name
    dst.write_bytes(raw_bytes)

    next_order = len(variant.images)
    img = SourceImage(
        id=str(uuid.uuid4()), variant_id=variant.id, name=final_name, src_path=str(dst),
        status=ImageStatus.READY.value,
        order_index=next_order,
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
    if img.status in (ImageStatus.CUTTING.value, ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value):
        raise HTTPException(409, "cannot delete an image while it is being processed; stop first")
    Path(img.src_path).unlink(missing_ok=True)
    db.delete(img)
    db.commit()


class ImagePatchRequest(BaseModel):
    scene_id: str | None = None  # null = 清除 per-image override，走 SKU 默认


@router.patch("/{sku_id}/images/{image_id}", response_model=SKUOut)
def patch_image(
    project_id: str, sku_id: str, image_id: str,
    payload: ImagePatchRequest,
    db: Session = Depends(get_session),
) -> dict:
    """改单图的 scene_id（per-image 模板覆盖）。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    img = db.get(SourceImage, image_id)
    if img is None or img.sku_id != sku_id:
        raise HTTPException(404, "image not found")
    if payload.scene_id is not None:
        from img2ec.models import Scene
        sc = db.get(Scene, payload.scene_id)
        if sc is None or sc.project_id != project_id:
            raise HTTPException(404, "scene not found in this project")
    img.scene_id = payload.scene_id
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


class ReorderRequest(BaseModel):
    image_ids: list[str]  # 期望的新顺序；必须正好等于该 variant 当前所有 image 的 id 集合


@router.post("/{sku_id}/variants/{variant_id}/images/reorder", response_model=SKUOut)
def reorder_images(
    project_id: str, sku_id: str, variant_id: str,
    payload: ReorderRequest,
    db: Session = Depends(get_session),
) -> dict:
    """整体重写该变体下原图的 order_index。前端拖拽完拿到完整新顺序 POST 过来。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    v = db.get(Variant, variant_id)
    if v is None or v.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    current_ids = {im.id for im in v.images}
    if set(payload.image_ids) != current_ids:
        raise HTTPException(
            400,
            f"reorder payload mismatch: expected {sorted(current_ids)}, got {sorted(set(payload.image_ids))}",
        )
    if len(payload.image_ids) != len(set(payload.image_ids)):
        raise HTTPException(400, "duplicate image id in payload")
    pos = {iid: i for i, iid in enumerate(payload.image_ids)}
    for im in v.images:
        im.order_index = pos[im.id]
    db.commit()
    db.refresh(sku)
    return _enrich(sku)
