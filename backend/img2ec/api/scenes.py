import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import Project, Scene
from img2ec.schemas.scene import SceneCreate, SceneOut

router = APIRouter(prefix="/api/projects/{project_id}/scenes", tags=["scenes"])


@router.get("", response_model=list[SceneOut])
def list_scenes(project_id: str, db: Session = Depends(get_session)) -> list[Scene]:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    return db.query(Scene).filter_by(project_id=project_id).all()


@router.post("", response_model=SceneOut, status_code=201)
def create_scene(project_id: str, payload: SceneCreate, db: Session = Depends(get_session)) -> Scene:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    sc = Scene(id=str(uuid.uuid4()), project_id=project_id, **payload.model_dump())
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.put("/{scene_id}", response_model=SceneOut)
def update_scene(project_id: str, scene_id: str, payload: SceneCreate, db: Session = Depends(get_session)) -> Scene:
    sc = db.get(Scene, scene_id)
    if sc is None or sc.project_id != project_id:
        raise HTTPException(404, "scene not found")
    for k, v in payload.model_dump().items():
        setattr(sc, k, v)
    db.commit()
    db.refresh(sc)
    return sc


@router.delete("/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_session)) -> None:
    sc = db.get(Scene, scene_id)
    if sc is None or sc.project_id != project_id:
        raise HTTPException(404, "scene not found")
    db.delete(sc)
    db.commit()
