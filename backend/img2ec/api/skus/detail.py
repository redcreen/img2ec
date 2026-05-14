from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir
from img2ec.models import SKU
from img2ec.schemas.sku import SKUOut
from img2ec.api.skus._helpers import DIMENSION_STYLES, _dimension_image_path_for_variant, _enrich

router = APIRouter()

class ApplyDimensionRequest(BaseModel):
    style: str = "white"  # "white" | "template"


class DetailComposeRequest(BaseModel):
    image_keys: list[str]  # 顺序敏感：master ratio (1x1/long/...) 或 size_white/size_template


@router.post("/{sku_id}/variants/{variant_id}/detail/compose", response_model=SKUOut, status_code=200)
def compose_detail_page(
    project_id: str, sku_id: str, variant_id: str,
    payload: DetailComposeRequest,
    db: Session = Depends(get_session),
) -> dict:
    """用用户选定的 image_keys 顺序重渲该变体在 3 平台的详情页。

    第一个 image_key 作为 hero（建议 1x1）；其余按顺序作为 full_image 或 size_diagram module。
    标题/卖点段始终保留（来自该变体的 PlatformOutputCopy）。
    """
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import variant_detail_path
    from img2ec.models import PlatformOutputCopy, Variant

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    primary = db.get(Variant, variant_id)
    if primary is None or primary.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    if not primary.images:
        raise HTTPException(400, "no images in variant")
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
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
    copies = db.query(PlatformOutputCopy).filter_by(variant_id=primary.id).all()
    if not copies:
        raise HTTPException(400, "no copy generated yet for this variant — wait then retry")

    for c in copies:
        copy_dict = {
            "title": c.title, "subtitle": c.subtitle,
            "selling_points": c.selling_points or [],
        }
        out_path = variant_detail_path(skud, primary, c.platform)
        render_detail_page(
            template=template, copy=copy_dict, images=images_dict,
            output_path=out_path, variants=variants_meta,
        )

    db.refresh(sku)
    return _enrich(sku)


@router.post("/{sku_id}/variants/{variant_id}/dimension/apply-to-detail", response_model=SKUOut, status_code=200)
def apply_dimension_to_detail(
    project_id: str, sku_id: str, variant_id: str,
    payload: ApplyDimensionRequest | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """把指定 style 的尺寸图作为 module 加入该变体的详情页底部并重渲 3 平台。"""
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import variant_detail_path
    from img2ec.models import PlatformOutputCopy, Variant

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    primary = db.get(Variant, variant_id)
    if primary is None or primary.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    if not primary.images:
        raise HTTPException(400, "no source images in variant")

    style = (payload.style if payload else "white") or "white"
    if style not in DIMENSION_STYLES:
        raise HTTPException(400, f"invalid style: {style}; allowed: {list(DIMENSION_STYLES)}")

    chosen_path = _dimension_image_path_for_variant(primary, style, 0)
    if chosen_path is None or not chosen_path.exists():
        raise HTTPException(400, f"dimension diagram for style={style} not generated yet")

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
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)

    copies = db.query(PlatformOutputCopy).filter_by(variant_id=primary.id).all()
    if not copies:
        raise HTTPException(400, "no copy generated yet for this variant — wait then retry")

    for c in copies:
        copy_dict = {
            "title": c.title, "subtitle": c.subtitle,
            "selling_points": c.selling_points or [],
        }
        out_path = variant_detail_path(skud, primary, c.platform)
        render_detail_page(
            template=template, copy=copy_dict, images=images_dict,
            output_path=out_path, variants=variants_meta,
        )

    db.refresh(sku)
    return _enrich(sku)
