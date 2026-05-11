import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.config import get_settings
from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir, ensure_sku_dirs, source_dir
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus, Variant
from img2ec.schemas.sku import SKUCreate, SKUDimensions, SKUOut

router = APIRouter(prefix="/api/projects/{project_id}/skus", tags=["skus"])


def _path_to_url(path: str | None) -> str | None:
    """Convert an absolute filesystem path under root_path to a /static/projects/... URL.
    URL-encodes path segments so `#`, `?`, spaces 等特殊字符在浏览器里能正确发请求（不被解析为 fragment/query）。"""
    if not path:
        return None
    root = str(get_settings().root_path)
    if path.startswith(root):
        rel = path[len(root):].lstrip("/")
        from urllib.parse import quote
        # 按 / 分段后逐段 quote，避免把分隔符也编码掉
        encoded = "/".join(quote(seg, safe="") for seg in rel.split("/"))
        return f"/static/projects/{encoded}"
    return None


DIMENSION_STYLES = ("white", "template")


def _dimension_image_path_for_variant(variant, style: str = "white", image_idx: int = 0) -> Path | None:
    """Variant 维度的尺寸图路径（按 image_idx 选 source）。
    文件名 = <该 source 的 stem>-dimension-<style>.jpg，所以多 source 不会冲突。
    """
    if not variant or not variant.images:
        return None
    if image_idx < 0 or image_idx >= len(variant.images):
        return None
    sku = variant.product
    if sku is None:
        return None
    proj = sku.project
    if proj is None:
        return None
    if style not in DIMENSION_STYLES:
        return None
    from img2ec.infra.fs_layout import variant_dir as variant_dir_fn
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    vdir = variant_dir_fn(skud, variant)
    image_stem = Path(variant.images[image_idx].name).stem
    return vdir / "outputs" / "dimension" / f"{image_stem}-dimension-{style}.jpg"


# 尺寸图后台生成状态：{variant_id: {"<style>_img<idx>": {status, err}}}
_DIM_STATE: dict[str, dict[str, dict]] = {}


def _enrich_variant(variant) -> dict:
    """序列化一个 variant 并注入计算字段（图片 URL、尺寸图 URL/状态）。"""
    from img2ec.schemas.sku import VariantOut
    out = VariantOut.model_validate(variant).model_dump()
    paths = variant.sku_thumb_paths or ([variant.sku_thumb_path] if variant.sku_thumb_path else [])
    out["sku_thumb_paths"] = paths
    out["sku_thumb_urls"] = [_path_to_url(p) or "" for p in paths]
    primary = variant.primary_thumb_path
    out["sku_thumb_path"] = primary
    out["sku_thumb_url"] = _path_to_url(primary) if primary else None
    for img in out["images"]:
        img["src_url"] = _path_to_url(img.get("src_path"))
        img["master_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("master_paths") or {}).items()
        }
        img["derived_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("derived_paths") or {}).items()
        }
    # 尺寸图：扫所有 (style, image_idx) 组合
    dim_urls: dict[str, str] = {}
    state = _DIM_STATE.get(variant.id, {})
    dim_states: dict[str, dict] = {}
    for style in DIMENSION_STYLES:
        for idx in range(len(variant.images)):
            key = f"{style}_img{idx}"
            p = _dimension_image_path_for_variant(variant, style, idx)
            if p is not None and p.exists():
                url = _path_to_url(str(p))
                if url:
                    dim_urls[key] = url
            # state per combo
            dim_states[key] = {
                "status": state.get(key, {}).get("status", "idle"),
                "err": state.get(key, {}).get("err"),
            }
        # 兼容字段：style 单写（指向 img0）
        single_key_url = dim_urls.get(f"{style}_img0")
        if single_key_url:
            dim_urls[style] = single_key_url
        dim_states[style] = dim_states.get(f"{style}_img0", {"status": "idle", "err": None})
    out["dimension_urls"] = dim_urls
    out["dimension_states"] = dim_states
    return out


def _enrich(sku: SKU) -> dict:
    """Serialize SKU + variants + 兼容字段（聚合 default variant 数据）。"""
    out = SKUOut.model_validate(sku).model_dump()
    # variants 列表（顺序：default 在前）
    out["variants"] = [_enrich_variant(v) for v in sku.variants]
    # images 兼容：聚合所有变体的图（前端可由 variants[].images 拆出，但保留聚合避免老代码炸）
    all_images: list[dict] = []
    for v_out in out["variants"]:
        all_images.extend(v_out["images"])
    out["images"] = all_images
    # 兼容字段：dimension_urls/states 取 default variant 的（前端老路径还在用）
    default_v = out["variants"][0] if out["variants"] else None
    out["dimension_urls"] = default_v["dimension_urls"] if default_v else {}
    out["dimension_states"] = default_v["dimension_states"] if default_v else {}
    return out


def _get_variant_or_default(sku: SKU, variant_id: str | None):
    """根据可选 variant_id 取 variant；未指定时返回 default。"""
    if variant_id is None:
        return sku.default_variant
    for v in sku.variants:
        if v.id == variant_id:
            return v
    return None


# 兼容旧调用：保留 _dimension_image_path 名字，但内部走 variant 版（用 default variant）
def _dimension_image_path(sku: SKU, style: str = "white") -> Path | None:
    return _dimension_image_path_for_variant(sku.default_variant, style)


@router.get("", response_model=list[SKUOut])
def list_skus(project_id: str, db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(SKU).filter_by(project_id=project_id).all()
    return [_enrich(s) for s in rows]


@router.post("", response_model=SKUOut, status_code=201)
def create_sku(project_id: str, payload: SKUCreate, db: Session = Depends(get_session)) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")
    sku = SKU(id=str(uuid.uuid4()), project_id=project_id, name=payload.name,
              scene_id=payload.scene_id, status=SKUStatus.DRAFT.value)
    db.add(sku)
    # 自动建默认变体；多色场景 Phase 4 加变体 CRUD
    db.add(Variant(
        id=str(uuid.uuid4()), product_id=sku.id, color_name="默认", status="draft",
    ))

    skud = sku_dir(Path(proj.root_path).parent, proj.name, payload.name)
    ensure_sku_dirs(skud)

    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.get("/{sku_id}", response_model=SKUOut)
def get_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    return _enrich(sku)


@router.delete("/{sku_id}", status_code=204)
def delete_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> None:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    db.delete(sku)
    db.commit()


@router.post("/{sku_id}/images", response_model=SKUOut, status_code=201)
def upload_image(
    project_id: str, sku_id: str,
    file: UploadFile = File(...),
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, project_id)

    variant = _get_variant_or_default(sku, variant_id)
    if variant is None:
        variant = Variant(
            id=str(uuid.uuid4()), product_id=sku.id, color_name="默认", status="draft",
        )
        db.add(variant)
        db.flush()

    from img2ec.infra.fs_layout import variant_dir as variant_dir_fn
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    vdir = variant_dir_fn(skud, variant)
    src_d = vdir / "source"
    src_d.mkdir(parents=True, exist_ok=True)
    dst = src_d / file.filename
    dst.write_bytes(file.file.read())

    img = SourceImage(
        id=str(uuid.uuid4()), variant_id=variant.id, name=file.filename, src_path=str(dst),
        status=ImageStatus.PENDING.value,
    )
    db.add(img)
    if sku.status == SKUStatus.DRAFT.value:
        sku.status = SKUStatus.READY.value
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.delete("/{sku_id}/images/{image_id}", status_code=204)
def delete_image(project_id: str, sku_id: str, image_id: str, db: Session = Depends(get_session)) -> None:
    img = db.get(SourceImage, image_id)
    if img is None or img.sku_id != sku_id:
        raise HTTPException(404, "image not found")
    if img.status in (ImageStatus.CUTTING.value, ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value):
        raise HTTPException(409, "cannot delete an image while it is being processed; stop first")
    Path(img.src_path).unlink(missing_ok=True)
    db.delete(img)
    db.commit()


VALID_RATIOS = {"1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"}
ORDERED_RATIOS = ["1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"]


@router.get("/{sku_id}/preview-prompt")
def preview_prompt(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    """返回该 SKU 当前 scene 拼装出的 5 个 ratio 完整 prompt（前端展示用）。"""
    from img2ec.infra.codex_image import build_master_prompt
    from img2ec.models import Scene

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    scene = db.get(Scene, sku.scene_id) if sku.scene_id else None
    if scene is None:
        raise HTTPException(400, "no scene assigned")

    return {
        "scene_name": scene.name,
        "scene_prompt": scene.prompt,
        "negative_prompt": scene.negative_prompt,
        "per_ratio": {
            r: build_master_prompt(scene_prompt=scene.prompt, ratio_key=r)
            for r in ORDERED_RATIOS
        },
    }


class ProcessRequest(BaseModel):
    ratios: list[str] | None = None  # None=全部 5 个；指定 ⊂ {"1x1","long","3x4","9x16","16x9"}


@router.post("/{sku_id}/process", status_code=202)
def process_sku(
    project_id: str, sku_id: str,
    payload: ProcessRequest | None = None,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """触发生成。
    - 无 variant_id：处理产品下所有变体（每变体跑自己的原图）
    - 指定 variant_id：只处理该变体
    - ratios 同前：未指定即全部 8 种规格
    """
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.scene_id is None:
        raise HTTPException(400, "no scene assigned")

    ratios = payload.ratios if payload else None
    if ratios is not None:
        if not ratios:
            raise HTTPException(400, "ratios cannot be empty list (omit field for all 8)")
        invalid = set(ratios) - VALID_RATIOS
        if invalid:
            raise HTTPException(400, f"invalid ratios: {sorted(invalid)}")
        wanted = sorted(ratios)
    else:
        wanted = sorted(VALID_RATIOS)

    if variant_id is not None:
        target_variants = [v for v in sku.variants if v.id == variant_id]
        if not target_variants:
            raise HTTPException(404, "variant not found")
    else:
        target_variants = list(sku.variants)

    if not any(v.images for v in target_variants):
        raise HTTPException(400, "no source images on SKU")

    sku.status = SKUStatus.RUNNING.value
    image_ids: list[str] = []
    for v in target_variants:
        for img in v.images:
            img.status = ImageStatus.PENDING.value
            img.err_msg = None
            image_ids.append(img.id)
    db.commit()

    import threading
    from img2ec.tasks.pipeline_tasks import process_image_task

    eager = get_settings().celery_eager
    if eager:
        for iid in image_ids:
            threading.Thread(
                target=process_image_task.delay,
                args=(iid, wanted),
                daemon=True,
            ).start()
    else:
        for iid in image_ids:
            process_image_task.delay(iid, wanted)

    return {"queued": len(image_ids), "ratios": wanted}


@router.post("/{sku_id}/cancel", status_code=200)
def cancel_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    """请求停止处理。Pipeline 会在下一个 master 完成后检测到并 bail；已生成的 master 保留。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.status != SKUStatus.RUNNING.value:
        raise HTTPException(400, f"only running SKU can be cancelled (current: {sku.status})")
    sku.status = "cancelled"
    db.commit()
    return {"ok": True}


class ApplyDimensionRequest(BaseModel):
    style: str = "white"  # "white" | "template"


class DetailComposeRequest(BaseModel):
    image_keys: list[str]  # 顺序敏感：master ratio (1x1/long/...) 或 size_white/size_template


@router.post("/{sku_id}/detail/compose", response_model=SKUOut, status_code=200)
def compose_detail_page(
    project_id: str, sku_id: str,
    payload: DetailComposeRequest,
    db: Session = Depends(get_session),
) -> dict:
    """用用户选定的 image_keys 顺序重渲 3 平台详情页。

    第一个 image_key 作为 hero（建议 1x1）；其余按顺序作为 full_image 或 size_diagram module。
    标题/卖点段始终保留（来自 PlatformOutputCopy）。
    """
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import platform_dir as platform_dir_fn
    from img2ec.models import PlatformOutputCopy

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    primary = sku.default_variant
    if primary is None or not primary.images:
        raise HTTPException(400, "no images in primary variant")
    if not payload.image_keys:
        raise HTTPException(400, "image_keys cannot be empty")

    images_dict: dict[str, Path] = {}
    modules_after_selling: list[dict] = []
    hero_key: str | None = None

    def _resolve(k: str) -> Path | None:
        """ratio key 解析：'img<idx>:<ratio>' / 'size_<style>[_img<N>]' / 旧 '<ratio>'（→ img0）"""
        if k.startswith("size_"):
            import re as _re
            rest = k[len("size_"):]
            m = _re.match(r"^(white|template)(?:_img(\d+))?$", rest)
            if not m:
                return None
            style = m.group(1)
            idx = int(m.group(2)) if m.group(2) is not None else 0
            p = _dimension_image_path_for_variant(primary, style, idx)
            return p if p and p.exists() else None
        if k.startswith("img"):
            import re
            m = re.match(r"img(\d+):(.+)", k)
            if not m:
                return None
            idx = int(m.group(1)); ratio = m.group(2)
            if idx >= len(primary.images):
                return None
            mp = primary.images[idx].master_paths or {}
            return Path(mp[ratio]) if ratio in mp else None
        # legacy: bind to img0
        mp = primary.images[0].master_paths or {} if primary.images else {}
        return Path(mp[k]) if k in mp else None

    for i, k in enumerate(payload.image_keys):
        path = _resolve(k)
        if path is None:
            continue
        images_dict[k] = path
        if k.startswith("size_"):
            modules_after_selling.append({"type": "size_diagram", "config": {"key": k, "title": "商品尺寸"}})
            continue
        # hero 优先：第一张以 1x1 结尾的当 hero；否则第一个非 size 的当 hero
        is_one_by_one = k == "1x1" or k.endswith(":1x1")
        if hero_key is None and is_one_by_one:
            hero_key = k
            # 同时绑定到 "1x1" key（hero module 看的 key）
            images_dict["1x1"] = path
            continue
        if i == 0 and hero_key is None:
            hero_key = k
            images_dict["1x1"] = path
            continue
        modules_after_selling.append({"type": "full_image", "config": {"_key": k}})

    if hero_key is None or "1x1" not in images_dict:
        raise HTTPException(400, "compose requires at least one 1x1 master in image_keys")

    # 多变体颜色对比块（自动）
    variants_meta = []
    if len(sku.variants) > 1:
        for v in sku.variants:
            v_img = v.images[0] if v.images else None
            m = (v_img.master_paths or {}).get("1x1") if v_img else None
            if m:
                variants_meta.append({"color_name": v.color_name, "image_path": Path(m)})

    modules = [
        {"type": "hero", "config": {"height": 750, "scale": 0.78, "bg_color": [248, 244, 238]}},
        {"type": "title_banner", "config": {"height": 280, "title_size": 40, "subtitle_size": 22}},
        {"type": "selling_points", "config": {"max_points": 3, "accent_color": [191, 130, 60]}},
    ]
    if len(variants_meta) >= 2:
        modules.append({"type": "color_comparison", "config": {}})
    modules.extend(modules_after_selling)

    template = {"canvas_width": DEFAULT_TEMPLATE["canvas_width"], "modules": modules}

    proj = sku.project
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    copies = db.query(PlatformOutputCopy).filter_by(sku_id=sku_id).all()
    if not copies:
        raise HTTPException(400, "no copy generated yet — wait for copy then retry")

    for c in copies:
        copy_dict = {
            "title": c.title, "subtitle": c.subtitle,
            "selling_points": c.selling_points or [],
        }
        out_path = platform_dir_fn(skud, c.platform) / "detail-template.jpg"
        render_detail_page(
            template=template, copy=copy_dict, images=images_dict,
            output_path=out_path, variants=variants_meta,
        )

    db.refresh(sku)
    return _enrich(sku)


@router.post("/{sku_id}/dimension/apply-to-detail", response_model=SKUOut, status_code=200)
def apply_dimension_to_detail(
    project_id: str, sku_id: str,
    payload: ApplyDimensionRequest | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """把指定 style 的尺寸图作为 module 加入详情页底部并重渲 3 平台详情页。"""
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import platform_dir as platform_dir_fn
    from img2ec.models import PlatformOutputCopy

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if not sku.images:
        raise HTTPException(400, "no source images")

    style = (payload.style if payload else "white") or "white"
    if style not in DIMENSION_STYLES:
        raise HTTPException(400, f"invalid style: {style}; allowed: {list(DIMENSION_STYLES)}")

    chosen_path = _dimension_image_path(sku, style)
    if chosen_path is None or not chosen_path.exists():
        raise HTTPException(400, f"dimension diagram for style={style} not generated yet")

    # 用主变体（默认变体）的 master 拼详情页；尺寸图作为附加 module
    primary = sku.default_variant
    if primary is None or not primary.images:
        raise HTTPException(400, "no images in primary variant")
    img = primary.images[0]
    master_paths = {k: Path(v) for k, v in (img.master_paths or {}).items()}
    images_dict = {**master_paths, f"size_{style}": chosen_path}
    if "1x1" not in images_dict:
        raise HTTPException(400, "1x1 master required for detail page")

    # 多变体颜色对比
    variants_meta = []
    if len(sku.variants) > 1:
        for v in sku.variants:
            v_img = v.images[0] if v.images else None
            m = (v_img.master_paths or {}).get("1x1") if v_img else None
            if m:
                variants_meta.append({"color_name": v.color_name, "image_path": Path(m)})

    modules = list(DEFAULT_TEMPLATE["modules"])
    if len(variants_meta) >= 2:
        new_mods = []
        for m in modules:
            new_mods.append(m)
            if m.get("type") == "selling_points":
                new_mods.append({"type": "color_comparison", "config": {}})
        modules = new_mods
    modules.append({"type": "size_diagram", "config": {"key": f"size_{style}", "title": "商品尺寸"}})

    template = {**DEFAULT_TEMPLATE, "modules": modules}

    proj = sku.project
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)

    copies = db.query(PlatformOutputCopy).filter_by(sku_id=sku_id).all()
    if not copies:
        raise HTTPException(400, "no copy generated yet — wait until copy is ready then retry")

    for c in copies:
        copy_dict = {
            "title": c.title, "subtitle": c.subtitle,
            "selling_points": c.selling_points or [],
        }
        out_path = platform_dir_fn(skud, c.platform) / "detail-template.jpg"
        render_detail_page(
            template=template, copy=copy_dict, images=images_dict,
            output_path=out_path, variants=variants_meta,
        )

    db.refresh(sku)
    return _enrich(sku)


@router.patch("/{sku_id}/dimensions", response_model=SKUOut)
def update_dimensions(
    project_id: str, sku_id: str,
    payload: SKUDimensions,
    db: Session = Depends(get_session),
) -> dict:
    """更新 SKU 物理尺寸（cm）。三项可分别为空。改尺寸后前端可单独触发 regenerate。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    sku.length_cm = payload.length_cm
    sku.width_cm = payload.width_cm
    sku.height_cm = payload.height_cm
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


class DimensionRegenerateRequest(BaseModel):
    styles: list[str] = ["white"]  # subset of {"white","template"}
    image_indices: list[int] | None = None  # 哪些原图（按 variant.images 索引）；None=只用第 0 张


@router.post("/{sku_id}/dimension/regenerate", response_model=SKUOut, status_code=202)
def regenerate_dimension_diagram(
    project_id: str, sku_id: str,
    payload: DimensionRegenerateRequest | None = None,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """异步为指定变体（缺省 default）生成尺寸图。"""
    from img2ec.models import Scene

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.length_cm is None or sku.width_cm is None or sku.height_cm is None:
        raise HTTPException(400, "all three dimensions (length/width/height) must be set")

    variant = _get_variant_or_default(sku, variant_id)
    if variant is None or not variant.images:
        raise HTTPException(400, "variant has no source images")

    requested = (payload.styles if payload else None) or ["white"]
    invalid = [s for s in requested if s not in DIMENSION_STYLES]
    if invalid:
        raise HTTPException(400, f"invalid styles: {invalid}; allowed: {list(DIMENSION_STYLES)}")
    if not requested:
        raise HTTPException(400, "styles cannot be empty")

    indices = (payload.image_indices if payload and payload.image_indices is not None else [0])
    bad_idx = [i for i in indices if i < 0 or i >= len(variant.images)]
    if bad_idx:
        raise HTTPException(400, f"image_indices out of range: {bad_idx}")
    if not indices:
        raise HTTPException(400, "image_indices cannot be empty")

    scene = db.get(Scene, sku.scene_id) if sku.scene_id else None
    if "template" in requested and (scene is None or not scene.prompt):
        raise HTTPException(400, "template style requires SKU to have a scene template assigned")

    # (style, idx) 组合
    combos = [(s, i) for s in requested for i in indices]
    state = _DIM_STATE.setdefault(variant.id, {})
    busy_combos = [f"{s}_img{i}" for s, i in combos if state.get(f"{s}_img{i}", {}).get("status") == "generating"]
    if busy_combos:
        raise HTTPException(409, f"already generating: {busy_combos}")

    for s, i in combos:
        state[f"{s}_img{i}"] = {"status": "generating", "err": None}

    sku_dims = (sku.length_cm, sku.width_cm, sku.height_cm)
    scene_prompt = scene.prompt if scene else None
    # 抓出每个 combo 的 src_path 和 out_path
    combo_specs: list[tuple[str, int, Path, Path]] = []
    for s, i in combos:
        src_path = Path(variant.images[i].src_path)
        if not src_path.exists():
            raise HTTPException(400, f"source image missing: {src_path}")
        out_path = _dimension_image_path_for_variant(variant, s, i)
        if out_path is None:
            raise HTTPException(500, f"cannot compute output path for {s}_img{i}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        combo_specs.append((s, i, src_path, out_path))

    vid = variant.id

    def _make_worker(style: str, idx: int, src_p: Path, out_p: Path):
        key = f"{style}_img{idx}"
        def _w() -> None:
            from img2ec.infra.codex_image import CodexImageError, generate_size_diagram
            try:
                generate_size_diagram(
                    source_image=src_p,
                    length_cm=sku_dims[0],
                    width_cm=sku_dims[1],
                    height_cm=sku_dims[2],
                    output_path=out_p,
                    style=style,
                    scene_prompt=scene_prompt,
                )
                _DIM_STATE[vid][key] = {"status": "idle", "err": None}
            except CodexImageError as e:
                _DIM_STATE[vid][key] = {"status": "error", "err": f"Codex error: {e}"}
            except Exception as e:
                _DIM_STATE[vid][key] = {"status": "error", "err": f"{type(e).__name__}: {e}"}
        return _w

    import threading
    for s, i, src_p, out_p in combo_specs:
        threading.Thread(target=_make_worker(s, i, src_p, out_p), daemon=True).start()

    db.refresh(sku)
    return _enrich(sku)
