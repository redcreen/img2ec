import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.config import get_settings
from img2ec.db import get_session
from img2ec.infra.fs_layout import project_dir, slug as fs_slug
from img2ec.models import Project, Scene, SKU
from img2ec.schemas.project import ProjectCreate, ProjectOut, ProjectPatch
from img2ec.seeds.default_scenes import DEFAULT_SCENES

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_session)) -> list[ProjectOut]:
    rows = db.query(Project).all()
    return [_to_out(p, db) for p in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_session)) -> ProjectOut:
    if db.query(Project).filter_by(name=payload.name).first():
        raise HTTPException(409, f"project '{payload.name}' already exists")

    settings = get_settings()
    pid = str(uuid.uuid4())
    pdir = project_dir(settings.root_path, payload.name)
    pdir.mkdir(parents=True, exist_ok=True)

    p = Project(id=pid, name=payload.name, desc=payload.desc, root_path=str(pdir))
    db.add(p)

    if payload.copy_default_scenes:
        for seed in DEFAULT_SCENES:
            db.add(Scene(
                id=str(uuid.uuid4()),
                project_id=pid,
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
            ))

    db.commit()
    db.refresh(p)
    return _to_out(p, db)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_session)) -> ProjectOut:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    return _to_out(p, db)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: str,
    payload: ProjectPatch,
    db: Session = Depends(get_session),
) -> ProjectOut:
    """改名 / 改描述。改名会重命名磁盘目录并把所有子资源里的绝对路径前缀替换。"""
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")

    # 改描述
    if payload.desc is not None:
        p.desc = payload.desc

    # 改名（含磁盘目录重命名 + 子路径前缀替换）
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(400, "项目名不能为空")
        if new_name != p.name:
            existing = db.query(Project).filter_by(name=new_name).first()
            if existing and existing.id != p.id:
                raise HTTPException(409, f"已存在同名项目「{new_name}」")
            settings = get_settings()
            old_dir = Path(p.root_path)
            new_dir = settings.root_path / fs_slug(new_name)
            if old_dir.exists() and not new_dir.exists():
                old_dir.rename(new_dir)
            elif new_dir.exists() and old_dir.exists() and old_dir.resolve() != new_dir.resolve():
                raise HTTPException(409, f"目标目录已存在：{new_dir}")
            old_str, new_str = str(old_dir), str(new_dir)

            def fix(s: str | None) -> str | None:
                if not s:
                    return s
                if s.startswith(old_str + "/"):
                    return new_str + s[len(old_str):]
                if s == old_str:
                    return new_str
                return s

            # 走遍该项目下所有 SKU → variant → image，把路径前缀全替换
            for sku in p.skus:
                for v in sku.variants:
                    if v.sku_thumb_path:
                        v.sku_thumb_path = fix(v.sku_thumb_path)
                    if v.sku_thumb_paths:
                        v.sku_thumb_paths = [fix(s) for s in v.sku_thumb_paths]
                    for im in v.images:
                        im.src_path = fix(im.src_path) or im.src_path
                        if im.master_paths:
                            im.master_paths = {k: fix(val) for k, val in im.master_paths.items()}
                        if im.master_history:
                            im.master_history = {
                                k: [fix(pp) for pp in lst]
                                for k, lst in im.master_history.items()
                            }
                        if im.derived_paths:
                            im.derived_paths = {k: fix(val) for k, val in im.derived_paths.items()}
            # 场景 ref_image_path 用相对路径（scene_covers/xxx.jpg），不需要改
            p.root_path = str(new_dir)
            p.name = new_name

    db.commit()
    db.refresh(p)
    return _to_out(p, db)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_session)) -> None:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    # 磁盘目录连带清掉（用户已经在 UI 上确认）
    import shutil
    root_path = Path(p.root_path)
    db.delete(p)
    db.commit()
    if root_path.exists() and root_path.is_dir():
        try:
            shutil.rmtree(root_path)
        except OSError:
            pass


def _to_out(p: Project, db: Session) -> ProjectOut:
    sku_count = db.query(SKU).filter_by(project_id=p.id).count()
    scene_count = db.query(Scene).filter_by(project_id=p.id).count()
    return ProjectOut.model_validate({
        "id": p.id, "name": p.name, "desc": p.desc, "root_path": p.root_path,
        "sku_count": sku_count, "scene_count": scene_count,
        "created_at": p.created_at, "updated_at": p.updated_at,
    })
