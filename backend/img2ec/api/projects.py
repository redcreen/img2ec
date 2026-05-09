import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.config import get_settings
from img2ec.db import get_session
from img2ec.infra.fs_layout import project_dir
from img2ec.models import Project, Scene, SKU
from img2ec.schemas.project import ProjectCreate, ProjectOut
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


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_session)) -> None:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    db.delete(p)
    db.commit()


def _to_out(p: Project, db: Session) -> ProjectOut:
    sku_count = db.query(SKU).filter_by(project_id=p.id).count()
    scene_count = db.query(Scene).filter_by(project_id=p.id).count()
    return ProjectOut.model_validate({
        "id": p.id, "name": p.name, "desc": p.desc, "root_path": p.root_path,
        "sku_count": sku_count, "scene_count": scene_count,
        "created_at": p.created_at, "updated_at": p.updated_at,
    })
