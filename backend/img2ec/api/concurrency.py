"""调整 Celery worker 并发数 — 运行时变 pool 大小。"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from img2ec.celery_app import celery_app

router = APIRouter(prefix="/api/concurrency", tags=["concurrency"])


class SetConcurrencyRequest(BaseModel):
    count: int = Field(..., ge=1, le=16)


def _current_pool_size() -> int | None:
    """读当前 worker pool 大小（取首个 worker；多 worker 时随便挑一个）。"""
    try:
        stats = celery_app.control.inspect(timeout=1.0).stats()
        if not stats:
            return None
        first = next(iter(stats.values()))
        # celery 5.x: stats['pool']['max-concurrency']
        return int(first.get("pool", {}).get("max-concurrency") or 0) or None
    except Exception:
        return None


@router.get("")
def get_concurrency() -> dict:
    cur = _current_pool_size()
    return {"current": cur, "min": 1, "max": 16}


@router.post("")
def set_concurrency(payload: SetConcurrencyRequest) -> dict:
    cur = _current_pool_size()
    if cur is None:
        raise HTTPException(503, "celery worker 没在跑 / inspect 超时")
    target = payload.count
    if target == cur:
        return {"current": cur, "delta": 0}
    delta = target - cur
    try:
        if delta > 0:
            celery_app.control.pool_grow(n=delta)
        else:
            celery_app.control.pool_shrink(n=-delta)
    except Exception as e:
        raise HTTPException(500, f"pool adjust failed: {e}")
    # 再读一次确认
    import time
    time.sleep(0.5)
    new_cur = _current_pool_size() or target
    return {"current": new_cur, "previous": cur, "delta": delta}
