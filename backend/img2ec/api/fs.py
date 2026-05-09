from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from img2ec.infra.reveal import reveal_in_finder

router = APIRouter(prefix="/api/fs", tags=["fs"])


class RevealReq(BaseModel):
    path: str


@router.post("/reveal", status_code=204)
def reveal(payload: RevealReq) -> None:
    if not payload.path:
        raise HTTPException(400, "path required")
    reveal_in_finder(payload.path)
