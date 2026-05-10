import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import outputs_dir, sku_dir
from img2ec.models import Project, SKU, SKUStatus

router = APIRouter(prefix="/api", tags=["outputs"])


@router.get("/skus/{sku_id}/download")
def download_sku_zip(sku_id: str, db: Session = Depends(get_session)):
    sku = db.get(SKU, sku_id)
    if sku is None:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, sku.project_id)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    outd = outputs_dir(skud)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in outd.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(outd))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{sku.name}.zip"'},
    )


@router.get("/projects/{project_id}/download-all")
def download_project_zip(project_id: str, db: Session = Depends(get_session)):
    """打包所有 done 状态 SKU 的 outputs/，每个 SKU 一个目录。"""
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")

    done_skus = [s for s in proj.skus if s.status == SKUStatus.DONE.value]
    if not done_skus:
        raise HTTPException(400, "no completed SKUs to download")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sku in done_skus:
            skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
            outd = outputs_dir(skud)
            if not outd.exists():
                continue
            for f in outd.rglob("*"):
                if f.is_file():
                    arcname = f"{sku.name}/{f.relative_to(outd)}"
                    zf.write(f, arcname=arcname)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{proj.name}-all.zip"'},
    )
