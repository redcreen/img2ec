import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import outputs_dir, sku_dir
from img2ec.models import Project, SKU

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
