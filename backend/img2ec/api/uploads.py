"""临时上传：参考图（reference image），只供本次生成使用。

不持久化到 DB；文件落到 IMG2EC_AI_PREVIEW_DIR（默认 /tmp/img2ec-ai-previews/），
靠操作系统清理。前端把返回的 path/url 存到 localStorage，刷新仍能看到缩略图，
processSku 时回传 path 给后端再校验。
"""
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/uploads", tags=["uploads"])

_REF_DIR = Path(tempfile.gettempdir()) / "img2ec-ai-previews"
_REF_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


def _validate_project(db: Session, project_id: str) -> Project:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")
    return proj


@router.post("/reference")
def upload_reference(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> dict:
    """存一张参考图到临时目录。返回 path / url；前端记到 genConfig。"""
    _validate_project(db, project_id)

    suffix = Path(file.filename or "ref.jpg").suffix.lower() or ".jpg"
    if suffix not in _ALLOWED_SUFFIX:
        raise HTTPException(400, f"unsupported suffix: {suffix}")

    data = file.file.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, f"file too large (>{_MAX_BYTES // 1024 // 1024} MB)")

    out = _REF_DIR / f"ref-{uuid.uuid4().hex[:12]}{suffix}"
    out.write_bytes(data)
    return {
        "path": str(out),
        "url": f"/static/ai-previews/{out.name}",
        "name": file.filename or out.name,
        "size": len(data),
    }


def validate_reference_path(p: str) -> Path:
    """processSku 时回收前端回传的 path：必须落在 _REF_DIR 里。"""
    path = Path(p).resolve()
    if _REF_DIR.resolve() not in path.parents and path.parent != _REF_DIR.resolve():
        raise HTTPException(400, f"reference path not under upload dir: {p}")
    if not path.is_file():
        raise HTTPException(400, f"reference image not found on disk: {p}")
    return path
