"""Celery task：生成单张尺寸图。独立于 uvicorn 进程，reload 不会打断。"""
from __future__ import annotations
from pathlib import Path

from img2ec.celery_app import celery_app
from img2ec.db import SessionLocal
from img2ec.infra import state_store
from img2ec.models import SKU


@celery_app.task(bind=True, max_retries=0)
def regenerate_dimension_task(
    self,
    sku_id: str,
    variant_id: str,
    style: str,
    image_idx: int,
) -> str:
    """生成 (style, image_idx) 这一张尺寸图。状态用 Redis 跨进程共享。"""
    from img2ec.api.skus._helpers import _dimension_image_path_for_variant
    from img2ec.infra.codex_image import CodexImageError, generate_size_diagram

    key = f"{style}_img{image_idx}"
    db = SessionLocal()
    try:
        sku = db.get(SKU, sku_id)
        if sku is None:
            return "sku_missing"
        variant = next((v for v in sku.variants if v.id == variant_id), None)
        if variant is None or image_idx >= len(variant.images):
            state_store.dim_set(variant_id, key, "error", "variant/image missing")
            return "missing"
        if sku.length_cm is None or sku.width_cm is None or sku.height_cm is None:
            state_store.dim_set(variant_id, key, "error", "尺寸未设置")
            return "no_dims"
        scene_prompt = None
        if style == "template":
            # 变体级覆盖 > SKU 默认
            from img2ec.models import Scene
            effective_scene_id = variant.scene_id or sku.scene_id
            scene = db.get(Scene, effective_scene_id) if effective_scene_id else None
            if scene is None or not scene.prompt:
                state_store.dim_set(variant_id, key, "error", "no scene for template style")
                return "no_scene"
            scene_prompt = scene.prompt

        src_path = Path(variant.images[image_idx].src_path)
        if not src_path.exists():
            state_store.dim_set(variant_id, key, "error", f"src missing: {src_path}")
            return "src_missing"
        out_path = _dimension_image_path_for_variant(variant, style, image_idx)
        if out_path is None:
            state_store.dim_set(variant_id, key, "error", "cannot compute output path")
            return "no_out"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            generate_size_diagram(
                source_image=src_path,
                length_cm=sku.length_cm,
                width_cm=sku.width_cm,
                height_cm=sku.height_cm,
                output_path=out_path,
                style=style,
                scene_prompt=scene_prompt,
            )
            state_store.dim_clear(variant_id, key)  # idle = 无 Redis 键
            return "ok"
        except CodexImageError as e:
            state_store.dim_set(variant_id, key, "error", f"Codex error: {e}")
            return "failed_codex"
        except Exception as e:
            state_store.dim_set(variant_id, key, "error", f"{type(e).__name__}: {e}")
            return "failed"
    finally:
        db.close()
