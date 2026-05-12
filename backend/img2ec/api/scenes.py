import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import Project, Scene
from img2ec.schemas.scene import SceneCreate, SceneOut
from img2ec.seeds.default_scenes import DEFAULT_SCENES

router = APIRouter(prefix="/api/projects/{project_id}/scenes", tags=["scenes"])


def _scene_to_out(sc: Scene) -> dict:
    """Serialize Scene + compute cover_url from ref_image_path.

    ref_image_path 约定：相对路径 'scene_covers/<file>.jpg' → /static/assets/scene_covers/<file>.jpg
    （留余地未来支持绝对路径或 /static/projects/... 路径，目前只处理 scene_covers/ 前缀）
    """
    out = SceneOut.model_validate(sc).model_dump()
    if sc.ref_image_path:
        path = sc.ref_image_path
        if path.startswith("scene_covers/"):
            out["cover_url"] = f"/static/assets/{path}"
        elif path.startswith("/"):
            # absolute filesystem path — best-effort: leave None unless under known root
            out["cover_url"] = None
        else:
            out["cover_url"] = f"/static/assets/{path}"
    return out


@router.get("", response_model=list[SceneOut])
def list_scenes(project_id: str, db: Session = Depends(get_session)) -> list[dict]:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    rows = db.query(Scene).filter_by(project_id=project_id).all()
    return [_scene_to_out(s) for s in rows]


def _adopt_cover(cover_path: str | None) -> str | None:
    """如果 payload 带了临时 cover_path（AI 端点生成的预览图），把它搬到 assets/scene_covers/
    并返回相对 ref_image_path。否则 None。"""
    if not cover_path:
        return None
    import shutil, uuid as _uuid
    src = Path(cover_path)
    if not src.exists():
        return None
    from img2ec.config import get_settings
    # backend/assets/scene_covers/ — 用 backend root 推算（main.py 已 mount /static/assets）
    repo_backend = Path(__file__).resolve().parent.parent.parent
    dst_dir = repo_backend / "assets" / "scene_covers"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"ai-{_uuid.uuid4().hex[:10]}{src.suffix or '.jpg'}"
    shutil.copy2(src, dst)
    return f"scene_covers/{dst.name}"


@router.post("", response_model=SceneOut, status_code=201)
def create_scene(project_id: str, payload: SceneCreate, db: Session = Depends(get_session)) -> dict:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    data = payload.model_dump()
    cover_path = data.pop("cover_path", None)
    ref_image_path = _adopt_cover(cover_path)
    sc = Scene(id=str(uuid.uuid4()), project_id=project_id,
               ref_image_path=ref_image_path, **data)
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return _scene_to_out(sc)


@router.put("/{scene_id}", response_model=SceneOut)
def update_scene(project_id: str, scene_id: str, payload: SceneCreate, db: Session = Depends(get_session)) -> dict:
    sc = db.get(Scene, scene_id)
    if sc is None or sc.project_id != project_id:
        raise HTTPException(404, "scene not found")
    data = payload.model_dump()
    cover_path = data.pop("cover_path", None)
    new_ref = _adopt_cover(cover_path)
    if new_ref:
        sc.ref_image_path = new_ref
    for k, v in data.items():
        setattr(sc, k, v)
    db.commit()
    db.refresh(sc)
    return _scene_to_out(sc)


@router.delete("/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_session)) -> None:
    sc = db.get(Scene, scene_id)
    if sc is None or sc.project_id != project_id:
        raise HTTPException(404, "scene not found")
    db.delete(sc)
    db.commit()


@router.post("/import-defaults", response_model=list[SceneOut], status_code=201)
def import_default_scenes(project_id: str, db: Session = Depends(get_session)) -> list[dict]:
    """导入默认模板（重名跳过）。代表图通过 ref_image_path = 'scene_covers/<file>' 注入。"""
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    existing_names = {n for (n,) in db.query(Scene.name).filter_by(project_id=project_id).all()}
    added: list[Scene] = []
    for seed in DEFAULT_SCENES:
        if seed.name in existing_names:
            continue
        sc = Scene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=seed.name,
            category=seed.category,
            desc=seed.desc,
            prompt=seed.prompt,
            negative_prompt=seed.negative_prompt,
            ip_adapter_weight=seed.ip_adapter_weight,
            base_model=seed.base_model,
            ref_image_path=f"scene_covers/{seed.cover_filename}" if seed.cover_filename else None,
            festival=seed.festival,
            created_by="system",
        )
        db.add(sc)
        added.append(sc)
    db.commit()
    for s in added:
        db.refresh(s)
    return [_scene_to_out(s) for s in added]
