"""AI 生成模板：关键词扩展 + 参考图反推 + 批量生成。

- /expand-from-keywords / /expand-from-reference 返回预览（前端确认后才入库）
- /batch-generate 直接造 N 张占位 Scene 入库，后台并发填充 prompt + cover
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from img2ec.db import SessionLocal, get_session
from img2ec.infra.codex_image import (
    CodexImageError,
    codex_text,
    generate_background_image,
)
from img2ec.models import Project, Scene
from img2ec.models.scene import FESTIVALS

router = APIRouter(prefix="/api/projects/{project_id}/scenes-ai", tags=["scenes-ai"])


class KeywordsExpandRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=8)
    festival: str = "通用"
    style: str = "新中式"  # 古风/新中式/国潮/民俗手作


class AIPreview(BaseModel):
    name: str
    desc: str
    prompt: str          # 英文 — 给 Codex 用的
    negative_prompt: str
    festival: str
    cover_path: str      # 服务端临时文件路径（前端创建模板时回传）
    cover_url: str       # /static/ai-previews/<uuid>.jpg
    raw_text: str = ""   # debug


_AI_PREVIEW_DIR = Path(tempfile.gettempdir()) / "img2ec-ai-previews"
_AI_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


# 节庆 × 关键词种子组合（用于批量生成 10 套）。
# 每个组合 → 一份独特角度的 prompt（同节庆里风格/场景/光线交错避免重复）
_BATCH_SEEDS: dict[str, list[tuple[list[str], str]]] = {
    "春节": [
        (["红木桌", "灯笼光", "梅花"], "新中式"),
        (["红绸缎", "金箔", "暖光"], "新中式"),
        (["门神", "福字", "暮色"], "民俗手作"),
        (["红梅", "青瓷", "晨光"], "古风"),
        (["八仙桌", "瓜果", "茶器"], "民俗手作"),
        (["墨色", "金红", "国潮"], "国潮"),
        (["红剪纸", "宫灯", "暖阁"], "古风"),
        (["雪窗", "对联", "暖橘"], "新中式"),
        (["朱漆", "玉饰", "高级"], "新中式"),
        (["年宵花", "粉桃", "清晨"], "新中式"),
    ],
    "元宵": [
        (["花灯", "汤圆", "暖光"], "新中式"),
        (["宫灯", "夜雪", "古风"], "古风"),
        (["猜灯谜", "灯笼", "夜市"], "民俗手作"),
        (["朱红", "金线", "团圆"], "新中式"),
        (["龙形花灯", "灯影", "墨夜"], "国潮"),
        (["茶香", "甜羹", "暖灶"], "民俗手作"),
        (["白雪", "红灯", "孤桥"], "古风"),
        (["纸糊兔灯", "童趣", "暖光"], "国潮"),
        (["瓜子糖果", "围炉", "笑语"], "民俗手作"),
        (["剪纸花灯", "墨红", "高级"], "新中式"),
    ],
    "端午": [
        (["艾草", "菖蒲", "窗光"], "新中式"),
        (["五色丝线", "麻布", "手作"], "民俗手作"),
        (["粽叶", "青瓷", "晨光"], "新中式"),
        (["青砖", "盆栽", "小院"], "古风"),
        (["龙舟", "暮光", "氛围"], "古风"),
        (["墨绿", "金线", "国潮"], "国潮"),
        (["朱砂", "雄黄", "古风"], "古风"),
        (["香囊", "丝穗", "暖光"], "民俗手作"),
        (["糯米", "竹篮", "粗陶"], "民俗手作"),
        (["端阳", "蒲剑", "雅致"], "新中式"),
    ],
    "七夕": [
        (["星河", "夜空", "暮色"], "国潮"),
        (["梅花", "鎏金", "粉调"], "新中式"),
        (["银针", "彩线", "乞巧"], "民俗手作"),
        (["月夜", "竹影", "诗意"], "古风"),
        (["双星", "鹊桥", "云霞"], "古风"),
        (["瓷瓶", "金箔", "玫瑰"], "新中式"),
        (["纸鸢", "红线", "情书"], "民俗手作"),
        (["薄纱", "桃花", "晨曦"], "新中式"),
        (["古琴", "信笺", "墨香"], "古风"),
        (["七巧板", "夜灯", "童心"], "国潮"),
    ],
    "中秋": [
        (["桂花", "圆月", "夜色"], "新中式"),
        (["月饼", "茶器", "礼盒"], "新中式"),
        (["墨蓝夜空", "云月", "诗意"], "古风"),
        (["茶席", "明月", "灯影"], "新中式"),
        (["竹篮", "玉兔", "童趣"], "民俗手作"),
        (["朱红", "金穗", "团圆"], "国潮"),
        (["白瓷", "桂花酒", "清雅"], "新中式"),
        (["山水画屏", "月色", "高级"], "古风"),
        (["柿子", "石榴", "暖橘"], "民俗手作"),
        (["纸窗", "灯笼", "夜雾"], "古风"),
    ],
    "重阳": [
        (["菊花", "秋叶", "暖阳"], "新中式"),
        (["书房", "古籍", "登高"], "古风"),
        (["茱萸", "山色", "远眺"], "古风"),
        (["重阳糕", "桂花", "茶香"], "民俗手作"),
        (["黄菊", "白瓷", "高级"], "新中式"),
        (["秋叶", "石阶", "暮色"], "古风"),
        (["竹简", "毛笔", "墨砚"], "古风"),
        (["金色稻穗", "粗陶", "晨光"], "民俗手作"),
        (["朱砂红", "国潮", "重阳"], "国潮"),
        (["孝亲", "暖灯", "围炉"], "民俗手作"),
    ],
    "腊八": [
        (["腊八粥", "豆罐", "暖灶"], "民俗手作"),
        (["寒梅", "雪窗", "冷调"], "新中式"),
        (["红枣", "桂圆", "暖橘"], "民俗手作"),
        (["银碗", "蜜糖", "高级"], "新中式"),
        (["瓦罐", "炉火", "古风"], "古风"),
        (["腊月", "寒梅", "宣纸"], "古风"),
        (["腊肉", "酱缸", "民俗"], "民俗手作"),
        (["雪地", "炊烟", "村舍"], "古风"),
        (["金黄稻穗", "粗布", "暖色"], "民俗手作"),
        (["朱红炉", "梅花", "墨意"], "国潮"),
    ],
    "通用": [
        (["白宣纸", "竹影", "留白"], "新中式"),
        (["青砖墙", "古朴", "暖光"], "古风"),
        (["黑檀木", "禅意", "高级"], "新中式"),
        (["茶席", "留香", "清雅"], "新中式"),
        (["麻布", "粗陶", "手作"], "民俗手作"),
        (["墨色", "金线", "现代"], "国潮"),
        (["竹编", "晨光", "自然"], "民俗手作"),
        (["山水画", "诗意", "古风"], "古风"),
        (["朱漆", "玉雕", "高级"], "新中式"),
        (["纸窗", "暖阳", "宁静"], "新中式"),
    ],
}


# ---------- helpers ----------

def _validate_project(db: Session, project_id: str) -> None:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")


def _validate_festival(s: str) -> str:
    return s if s in FESTIVALS else "通用"


def _extract_json(raw: str) -> dict:
    """Codex 偶尔在文本里夹 markdown 代码块；尽量抠出 JSON。"""
    # 直接尝试
    try:
        return json.loads(raw)
    except Exception:
        pass
    # ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 第一个 { 到最后一个 }
    s = raw.find("{"); e = raw.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(raw[s:e+1])
        except Exception:
            pass
    raise HTTPException(502, f"Codex returned non-JSON: {raw[:200]!r}")


def _build_keyword_prompt(keywords: list[str], festival: str, style: str) -> str:
    return f"""You are a senior Chinese e-commerce product photography art director.

Given:
- Festival: {festival}
- Style: {style}
- User keywords (Chinese, comma-separated): {", ".join(keywords)}

Compose a scene-only background prompt (NO product) suitable for Chinese e-commerce
product photography. The target product is a small Chinese folk-craft hanging
ornament or decoration (挂件/摆件/香囊). The scene must:
- match the festival cultural elements,
- match the requested style tone (古风=traditional, 新中式=refined modern,
  国潮=bold modern guo-chao, 民俗手作=rustic handmade),
- describe foreground placement surface + softly-blurred midground props
  + lighting + atmosphere, all suitable for product placement,
- explicitly state "no product visible, no text, no logo, no watermark".

Output ONLY valid JSON (no markdown fences) with keys:
  "name":            Chinese short title (≤14 chars, e.g. "端午·艾草·窗光")
  "desc":            Chinese one-line description (≤40 chars, what kind of product fits)
  "prompt":          English scene-only prompt (1 long sentence, ≥80 words, ≤200)
  "negative_prompt": English negative prompt (cluttered, watermark, etc.)
  "festival":        one of: 通用 / 春节 / 元宵 / 端午 / 七夕 / 中秋 / 重阳 / 腊八
"""


def _build_reference_prompt(festival: str, style: str) -> str:
    return f"""You are a senior Chinese e-commerce product photography art director.

Look at the provided reference image. Reverse-engineer what makes this scene work:
- foreground surface (material, texture, lighting on it)
- midground props (out of focus, character of objects)
- background atmosphere
- lighting direction, color temperature, mood
- color palette and overall aesthetic

Now compose a scene-only background prompt that, when given to a text-to-image
model, would reproduce the SAME aesthetic — but with NO product (the goal is a
background that Chinese folk-craft hanging ornaments / 挂件 / 摆件 / 香囊
could be placed onto).

Context:
- Festival: {festival}
- Style hint: {style}

Output ONLY valid JSON (no markdown fences) with keys:
  "name":            Chinese short title (≤14 chars, describe scene + lighting)
  "desc":            Chinese one-line description (≤40 chars, what kind of product fits)
  "prompt":          English scene-only prompt (1 long sentence, ≥100 words, ≤220)
  "negative_prompt": English negative prompt
  "festival":        one of: 通用 / 春节 / 元宵 / 端午 / 七夕 / 中秋 / 重阳 / 腊八
"""


def _generate_preview_cover(prompt: str) -> tuple[Path, str]:
    """用 prompt 跑一张 1:1 cover，返回 (path, url)。"""
    pid_ = uuid.uuid4().hex[:10]
    out = _AI_PREVIEW_DIR / f"ai-{pid_}.jpg"
    generate_background_image(prompt=prompt, ratio_key="1x1", output_path=out, timeout=600)
    return out, f"/static/ai-previews/{out.name}"


# ---------- endpoints ----------

@router.post("/expand-from-keywords", response_model=AIPreview)
def expand_from_keywords(
    project_id: str,
    payload: KeywordsExpandRequest,
    db: Session = Depends(get_session),
) -> dict:
    _validate_project(db, project_id)
    festival = _validate_festival(payload.festival)

    sys_prompt = _build_keyword_prompt(payload.keywords, festival, payload.style)
    try:
        raw = codex_text(prompt=sys_prompt, timeout=120)
    except CodexImageError as e:
        raise HTTPException(502, f"Codex text error: {e}")
    except Exception as e:
        raise HTTPException(502, f"text call interrupted: {e}")

    parsed = _extract_json(raw)
    name = (parsed.get("name") or "").strip()[:60]
    desc = (parsed.get("desc") or "").strip()[:200]
    eng_prompt = (parsed.get("prompt") or "").strip()
    neg = (parsed.get("negative_prompt") or "").strip()
    fest_out = _validate_festival(parsed.get("festival") or festival)
    if not (name and eng_prompt):
        raise HTTPException(502, f"Codex returned incomplete JSON: {parsed}")

    try:
        cover_path, cover_url = _generate_preview_cover(eng_prompt)
    except CodexImageError as e:
        raise HTTPException(502, f"cover render failed: {e}")
    except Exception as e:
        raise HTTPException(502, f"cover render interrupted: {e}")

    return {
        "name": name,
        "desc": desc,
        "prompt": eng_prompt,
        "negative_prompt": neg,
        "festival": fest_out,
        "cover_path": str(cover_path),
        "cover_url": cover_url,
        "raw_text": raw[:2000],
    }


class BatchGenerateRequest(BaseModel):
    festival: str = "通用"
    count: int = Field(10, ge=1, le=20)


class QueueKeywordsRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=8)
    festival: str = "通用"
    style: str = "新中式"


def _adopt_cover_into_assets(cover_src: Path) -> str:
    """把 cover 文件搬到 backend/assets/scene_covers/ai-*.jpg，返回相对 ref_image_path。"""
    repo_backend = Path(__file__).resolve().parent.parent.parent
    dst_dir = repo_backend / "assets" / "scene_covers"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"ai-{uuid.uuid4().hex[:10]}.jpg"
    shutil.copy2(cover_src, dst)
    return f"scene_covers/{dst.name}"


def _batch_worker(project_id: str, scene_id: str, keywords: list[str],
                  festival: str, style: str) -> None:
    """单个 batch 子任务：跑 Codex 文本 + cover，更新 DB scene。"""
    db = SessionLocal()
    try:
        sc = db.get(Scene, scene_id)
        if sc is None:
            return
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
        except Exception as e:
            sc.desc = f"生成失败：{type(e).__name__}: {e}"[:200]
            sc.category = f"AI · {festival} · 失败"
            db.commit()
    finally:
        db.close()


@router.post("/batch-generate")
def batch_generate(
    project_id: str,
    payload: BatchGenerateRequest,
    db: Session = Depends(get_session),
) -> dict:
    """批量生成 N 个该节庆下的模板。立即返回占位 Scene，后台并发填充。"""
    _validate_project(db, project_id)
    festival = _validate_festival(payload.festival)
    seed_combos = _BATCH_SEEDS.get(festival, _BATCH_SEEDS["通用"])[: payload.count]
    if not seed_combos:
        raise HTTPException(400, f"no seeds for festival {festival}")

    # 占位 scene 入库（前端立刻能看到 N 张"生成中"卡片）
    placeholders: list[str] = []
    for i, (kw, style) in enumerate(seed_combos, 1):
        sid = str(uuid.uuid4())
        sc = Scene(
            id=sid, project_id=project_id,
            name=f"⏳ AI 生成中 · {festival} {i}",
            category=f"AI · {festival} · 生成中",
            desc=f"关键词：{', '.join(kw)} · 风格：{style}",
            prompt="(generating)",
            negative_prompt="",
            festival=festival,
            created_by="ai_keywords",
        )
        db.add(sc)
        placeholders.append(sid)
    db.commit()

    # 派工到 celery worker — 独立进程，不受 uvicorn reload 影响
    from img2ec.tasks.scene_tasks import fill_ai_scene_task
    for sid, (kw, style) in zip(placeholders, seed_combos):
        fill_ai_scene_task.delay(sid, kw, festival, style)

    return {"scene_ids": placeholders, "count": len(placeholders), "festival": festival}


@router.post("/queue-from-keywords")
def queue_from_keywords(
    project_id: str,
    payload: QueueKeywordsRequest,
    db: Session = Depends(get_session),
) -> dict:
    """Fire-and-forget 关键词模板生成。立即返回占位 Scene id，后台填充。"""
    _validate_project(db, project_id)
    festival = _validate_festival(payload.festival)
    keywords = [k.strip() for k in payload.keywords if k.strip()][:8]
    if not keywords:
        raise HTTPException(400, "keywords cannot be empty")
    sid = str(uuid.uuid4())
    sc = Scene(
        id=sid, project_id=project_id,
        name=f"⏳ AI · {', '.join(keywords[:3])}",
        category=f"AI · {festival} · 生成中",
        desc=f"关键词：{', '.join(keywords)} · 风格：{payload.style}",
        prompt="(generating)",
        negative_prompt="",
        festival=festival,
        created_by="ai_keywords",
    )
    db.add(sc); db.commit()
    from img2ec.tasks.scene_tasks import fill_ai_scene_task
    fill_ai_scene_task.delay(sid, keywords, festival, payload.style)
    return {"scene_id": sid, "festival": festival}


@router.post("/expand-from-reference", response_model=AIPreview)
def expand_from_reference(
    project_id: str,
    reference: UploadFile = File(...),
    festival: str = Form("通用"),
    style: str = Form("新中式"),
    db: Session = Depends(get_session),
) -> dict:
    _validate_project(db, project_id)
    festival = _validate_festival(festival)

    # save upload to a temp file for codex -i
    suffix = Path(reference.filename or "ref.jpg").suffix or ".jpg"
    tmp = _AI_PREVIEW_DIR / f"upload-{uuid.uuid4().hex[:10]}{suffix}"
    with tmp.open("wb") as f:
        f.write(reference.file.read())

    sys_prompt = _build_reference_prompt(festival, style)
    try:
        raw = codex_text(prompt=sys_prompt, input_image=tmp, timeout=120)
    except CodexImageError as e:
        raise HTTPException(502, f"Codex vision error: {e}")
    except Exception as e:  # subprocess 被 reload 杀掉 / 任何意外
        raise HTTPException(502, f"vision call interrupted: {e}")
    finally:
        try: tmp.unlink()
        except OSError: pass

    parsed = _extract_json(raw)
    name = (parsed.get("name") or "").strip()[:60]
    desc = (parsed.get("desc") or "").strip()[:200]
    eng_prompt = (parsed.get("prompt") or "").strip()
    neg = (parsed.get("negative_prompt") or "").strip()
    fest_out = _validate_festival(parsed.get("festival") or festival)
    if not (name and eng_prompt):
        raise HTTPException(502, f"Codex returned incomplete JSON: {parsed}")

    try:
        cover_path, cover_url = _generate_preview_cover(eng_prompt)
    except CodexImageError as e:
        raise HTTPException(502, f"cover render failed: {e}")
    except Exception as e:
        raise HTTPException(502, f"cover render interrupted: {e}")

    return {
        "name": name,
        "desc": desc,
        "prompt": eng_prompt,
        "negative_prompt": neg,
        "festival": fest_out,
        "cover_path": str(cover_path),
        "cover_url": cover_url,
        "raw_text": raw[:2000],
    }
