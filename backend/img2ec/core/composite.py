"""Composite商品 cutout (RGBA, transparent bg) onto AI-generated scene background.

Path A architecture (Phase 2.1+):
- AI generates only the scene background (no IPAdapter).
- This module places the商品 cutout onto the background, preserving商品 100%.

Default placement: scale cutout to fit within `scale_pct` of canvas (preserving aspect),
center horizontally, anchor vertically per ratio (most ratios center; long is top-anchored
so the bottom can hold detail-page text).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

# Per-ratio scale (商品 longest-side as fraction of canvas longest-side) + y-anchor.
# scale_pct closer to 1.0 → 商品 fills more of canvas, less whitespace, more detail visible.
# 之前 0.5-0.7 的设置导致商品过小，无法展示细节。提高到 0.85-0.92。
_RATIO_PLACEMENT: dict[str, tuple[float, float]] = {
    "1x1":  (0.88, 0.55),
    "long": (0.85, 0.18),  # top region; bottom 60% still reserved for detail-page composition
    "3x4":  (0.88, 0.52),
    "9x16": (0.78, 0.42),  # tall canvas — 商品 wide-side fits canvas width well at 0.78
    "16x9": (0.85, 0.52),  # wide canvas — 商品 tall-side fills more of vertical space
}


def _make_drop_shadow(rgba: Image.Image, blur_px: int = 12, opacity: int = 70, offset: tuple[int, int] = (0, 14)) -> Image.Image:
    """Build a soft drop shadow from商品 alpha channel."""
    if rgba.mode != "RGBA":
        rgba = rgba.convert("RGBA")
    alpha = rgba.split()[-1]
    shadow = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, opacity), mask=alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_px))
    # offset the shadow
    out = Image.new("RGBA", (rgba.size[0] + offset[0], rgba.size[1] + offset[1]), (0, 0, 0, 0))
    out.paste(shadow, offset)
    return out


def composite_cutout_on_background(
    cutout_path: Path,
    background_path: Path,
    output_path: Path,
    *,
    ratio_key: str,
    scale_pct: float | None = None,
    y_anchor: float | None = None,
    drop_shadow: bool = True,
) -> Path:
    """Place cutout onto background and save as JPEG.

    Args:
        cutout_path: RGBA PNG of cutout商品 (transparent bg)
        background_path: AI-generated RGB JPEG scene background
        output_path: where to save result (JPEG)
        ratio_key: one of {"1x1", "long", "3x4", "9x16", "16x9"}; controls placement
        scale_pct: override default scale (商品 longest side / canvas longest side)
        y_anchor: override default vertical anchor (0=top, 0.5=center, 1=bottom)
        drop_shadow: add soft drop shadow under商品 for natural sit
    """
    default_scale, default_y = _RATIO_PLACEMENT.get(ratio_key, (0.65, 0.5))
    s = scale_pct if scale_pct is not None else default_scale
    ya = y_anchor if y_anchor is not None else default_y

    with Image.open(background_path) as bg_img:
        bg = bg_img.convert("RGB").copy()
    with Image.open(cutout_path) as cut_img:
        cut = cut_img.convert("RGBA").copy()

    cut = _crop_to_cutout_bbox(cut)

    bg_w, bg_h = bg.size
    cut_w, cut_h = cut.size
    # Fit商品 into a target box (scale_pct × canvas) preserving aspect ratio.
    # 商品 fills at least one dimension to scale_pct × that canvas dim, never overflows.
    # 比之前 min(bg_w, bg_h) 更激进 — 横版/竖版画布商品都能占画面主导。
    target_w = bg_w * s
    target_h = bg_h * s
    if cut_w / target_w >= cut_h / target_h:
        new_w = int(target_w)
        new_h = int(cut_h * (target_w / cut_w))
    else:
        new_h = int(target_h)
        new_w = int(cut_w * (target_h / cut_h))
    cut_resized = cut.resize((new_w, new_h), Image.LANCZOS)

    x = (bg_w - new_w) // 2
    y = int((bg_h - new_h) * ya)

    # Composite: bg → shadow → cutout
    canvas = bg.convert("RGBA")
    if drop_shadow:
        shadow_layer = _make_drop_shadow(cut_resized)
        # paste shadow at商品 position (offset already inside shadow)
        canvas.alpha_composite(shadow_layer, (x, y))
    canvas.alpha_composite(cut_resized, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "JPEG", quality=92)
    return output_path


def _crop_to_cutout_bbox(rgba: Image.Image) -> Image.Image:
    """Tighten商品 to its visible alpha bounding box (drop transparent padding)."""
    bbox = rgba.split()[-1].getbbox()
    return rgba.crop(bbox) if bbox else rgba
