from pathlib import Path

from img2ec.config import get_settings
from img2ec.infra.codex_image import DIMENSION_STYLES
from img2ec.infra.fs_layout import sku_dir
from img2ec.models import SKU
from img2ec.schemas.sku import SKUOut

VALID_RATIOS = {"1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"}
ORDERED_RATIOS = ["1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"]


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
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
    vdir = variant_dir_fn(skud, variant)
    image_stem = Path(variant.images[image_idx].name).stem
    return vdir / "outputs" / "dimension" / f"{image_stem}-dimension-{style}.jpg"


# 尺寸图状态已迁到 Redis（infra.state_store）；这里只是为兼容 import 名而保留空 dict
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
        # 历史版本：dict[ratio, list[{path, url}]]，新→旧，list[0] = primary
        hist_raw = img.get("master_history") or {}
        # 兜底：history 为空但 master_paths 有 → 自动用 primary 作单元素历史
        if not hist_raw and (img.get("master_paths") or {}):
            hist_raw = {k: [v] for k, v in (img["master_paths"] or {}).items() if v}
        img["master_history_urls"] = {
            k: [{"path": p, "url": _path_to_url(p) or ""} for p in (paths_list or [])]
            for k, paths_list in hist_raw.items()
        }
        img["derived_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("derived_paths") or {}).items()
        }
    # 注入每张原图的"排队中的 ratio 集合"（让前端只对这几格显示生成中）
    from img2ec.infra import state_store
    for img in out["images"]:
        img["pending_ratios"] = sorted(state_store.pending_ratios_get(img["id"]))
    # 尺寸图：扫所有 (style, image_idx) 组合；状态从 Redis 跨进程读
    dim_urls: dict[str, str] = {}
    state = state_store.dim_get_all(variant.id)
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
