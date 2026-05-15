"""Celery 任务：异步重生成变体文案 + 详情页拼图。

regenerate_copy_task：替代之前 /copy/regenerate 端点的同步阻塞实现。
Codex LLM 调用 1-3 分钟，同步会让前端按钮一直转圈、刷新还会丢请求。
改成 fire-and-forget：端点 setex redis 标记 + 入队即返回 202；任务跑完
重写 copy + render detail-template，最后清掉标记。前端只看 copy.regenerating
flag 决定是否还显示"生成中"。
"""
from __future__ import annotations
from pathlib import Path

from img2ec.celery_app import celery_app
from img2ec.db import SessionLocal
from img2ec.models import PlatformOutputCopy, SKU, Scene, Variant


@celery_app.task(bind=True, max_retries=0)
def regenerate_copy_task(self, project_id: str, sku_id: str, variant_id: str) -> str:
    from img2ec.core.copy_gen import generate_copy_for_sku
    from img2ec.infra.fs_layout import sku_dir as sku_dir_fn
    from img2ec.infra.llm_provider import CodexCLIProvider, LLMProviderError
    from img2ec.infra import state_store
    from img2ec.tasks.pipeline_tasks import _persist_copy, _render_detail_pages

    db = SessionLocal()
    try:
        sku = db.get(SKU, sku_id)
        if sku is None or sku.project_id != project_id:
            return "sku_missing"
        variant = db.get(Variant, variant_id)
        if variant is None or variant.product_id != sku.id:
            return "variant_missing"
        ref_img = next(
            (im for im in variant.images
             if im.master_paths and im.master_paths.get("1x1")),
            None,
        )
        if ref_img is None:
            return "no_master"

        effective_scene_id = variant.scene_id or sku.scene_id
        scene = db.get(Scene, effective_scene_id) if effective_scene_id else None

        try:
            result = generate_copy_for_sku(
                provider=CodexCLIProvider(),
                image_path=Path(ref_img.master_paths["1x1"]),
                sku_name=sku.name,
                scene_name=scene.name if scene else "",
                scene_category=scene.category if scene else "",
            )
        except LLMProviderError as e:
            return f"llm_failed: {e}"

        # 写完才删旧（避免中间态用户看到空文案）
        db.query(PlatformOutputCopy).filter_by(variant_id=variant.id).delete()
        _persist_copy(db, variant.id, result)

        proj = sku.project
        if proj:
            try:
                skud = sku_dir_fn(
                    Path(proj.root_path).parent, proj.name, sku.name, sku.id,
                )
                _render_detail_pages(db, variant.id, skud, ref_img.master_paths or {})
            except Exception:
                pass  # 详情页失败不挡文案，前端可手动重渲
        return "done"
    finally:
        state_store.copy_regen_clear(variant_id)
        db.close()
