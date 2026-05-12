"""Celery tasks for AI 场景生成（关键词扩展 单张 / 批量）。

每个 task 独立：codex_text → 解析 JSON → codex 生成 cover → 落 backend/assets/scene_covers/ → 更新 Scene DB 行。
"""
from __future__ import annotations
import shutil
import uuid
from pathlib import Path

from img2ec.celery_app import celery_app
from img2ec.db import SessionLocal
from img2ec.models import Scene


def _adopt_cover_into_assets(cover_src: Path) -> str:
    repo_backend = Path(__file__).resolve().parent.parent.parent
    dst_dir = repo_backend / "assets" / "scene_covers"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"ai-{uuid.uuid4().hex[:10]}.jpg"
    shutil.copy2(cover_src, dst)
    return f"scene_covers/{dst.name}"


@celery_app.task(bind=True, max_retries=0)
def fill_ai_scene_task(
    self,
    scene_id: str,
    keywords: list[str],
    festival: str,
    style: str,
) -> str:
    """填充 ai-keywords 模板：跑 Codex 文本 → 生成 cover → 更新 Scene。"""
    # 延迟导入避免循环
    from img2ec.api.ai_scenes import (
        _build_keyword_prompt, _extract_json, _generate_preview_cover,
    )
    from img2ec.infra.codex_image import codex_text
    from img2ec.models.scene import FESTIVALS

    db = SessionLocal()
    try:
        sc = db.get(Scene, scene_id)
        if sc is None:
            return "missing"
        try:
            raw = codex_text(prompt=_build_keyword_prompt(keywords, festival, style), timeout=120)
            parsed = _extract_json(raw)
            name = (parsed.get("name") or "").strip()[:60] or f"AI · {festival} · {','.join(keywords)}"
            desc = (parsed.get("desc") or "").strip()[:200]
            eng_prompt = (parsed.get("prompt") or "").strip()
            neg = (parsed.get("negative_prompt") or "").strip()
            fest_out = parsed.get("festival") or festival
            if fest_out not in FESTIVALS:
                fest_out = festival
            if not eng_prompt:
                raise RuntimeError(f"empty prompt: {parsed}")
            cover_path, _ = _generate_preview_cover(eng_prompt)
            ref_path = _adopt_cover_into_assets(cover_path)

            sc.name = name
            sc.desc = desc
            sc.prompt = eng_prompt
            sc.negative_prompt = neg
            sc.festival = fest_out
            sc.category = f"AI · {fest_out} · {style}"
            sc.ref_image_path = ref_path
            sc.created_by = "ai_keywords"
            db.commit()
            return "ok"
        except Exception as e:
            sc.desc = f"生成失败：{type(e).__name__}: {e}"[:200]
            sc.category = f"AI · {festival} · 失败"
            db.commit()
            return "failed"
    finally:
        db.close()
