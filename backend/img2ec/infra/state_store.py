"""跨进程的临时状态存储（Redis-backed）。

uvicorn handler 设状态（"running" / "error"）→ celery worker 读取并最终写"idle" / "error" → 前端 enrich 时读取。
之前用 module-global dict，跨进程不可见；改用 Redis 解决。
"""
from __future__ import annotations
import json
from typing import Any

import redis

from img2ec.config import get_settings

_client: redis.Redis | None = None


def _r() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


_DIM_PREFIX = "img2ec:dim:"
_DIM_TTL = 3600  # 1 小时清
_PENDING_RATIOS_PREFIX = "img2ec:pending_ratios:"  # 每张原图当前在排/在跑的 ratio set
_PENDING_RATIOS_TTL = 3600


def dim_set(variant_id: str, key: str, status: str, err: str | None = None) -> None:
    _r().setex(
        f"{_DIM_PREFIX}{variant_id}:{key}",
        _DIM_TTL,
        json.dumps({"status": status, "err": err}),
    )


def dim_get_all(variant_id: str) -> dict[str, dict]:
    """变体所有 dim 状态：{<style>_img<N>: {status, err}}"""
    out: dict[str, dict] = {}
    pattern = f"{_DIM_PREFIX}{variant_id}:*"
    for k in _r().scan_iter(match=pattern, count=200):
        try:
            v = _r().get(k)
            if not v:
                continue
            data = json.loads(v)
            key = k.split(":", 3)[-1]
            out[key] = data
        except Exception:
            continue
    return out


def dim_clear(variant_id: str, key: str) -> None:
    _r().delete(f"{_DIM_PREFIX}{variant_id}:{key}")


# === per-image 排队中的 ratio 集合 ===

def pending_ratios_set(image_id: str, ratios: list[str]) -> None:
    """覆盖式设置：该原图当前在排/在跑的 ratio 列表。"""
    key = f"{_PENDING_RATIOS_PREFIX}{image_id}"
    pipe = _r().pipeline()
    pipe.delete(key)
    if ratios:
        pipe.sadd(key, *ratios)
        pipe.expire(key, _PENDING_RATIOS_TTL)
    pipe.execute()


def pending_ratios_add(image_id: str, ratios: list[str]) -> None:
    """增量添加：把新 ratio 加到原有 set 里（已有的图也能继续 enqueue）。"""
    if not ratios:
        return
    key = f"{_PENDING_RATIOS_PREFIX}{image_id}"
    pipe = _r().pipeline()
    pipe.sadd(key, *ratios)
    pipe.expire(key, _PENDING_RATIOS_TTL)
    pipe.execute()


def pending_ratios_remove(image_id: str, ratio: str) -> None:
    _r().srem(f"{_PENDING_RATIOS_PREFIX}{image_id}", ratio)


def pending_ratios_get(image_id: str) -> set[str]:
    return _r().smembers(f"{_PENDING_RATIOS_PREFIX}{image_id}") or set()


def pending_ratios_clear(image_id: str) -> None:
    _r().delete(f"{_PENDING_RATIOS_PREFIX}{image_id}")
