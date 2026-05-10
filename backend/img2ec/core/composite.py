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
    # 把商品压在画面下半部，让它"落"在桌面线上而不是悬浮。0.65 让商品中心位于 65% 高度处。
    "1x1":  (0.80, 0.62),
    "long": (0.78, 0.48),  # 长图：商品中部偏上，下方桌面延伸 + 商品 = 自然 (不悬浮)
    "3x4":  (0.80, 0.60),
    "9x16": (0.72, 0.55),  # tall canvas
    "16x9": (0.78, 0.62),  # wide canvas
}


def _make_shadow_layer(
    rgba: Image.Image,
    *,
    blur_px: int,
    opacity: int,
    offset: tuple[int, int],
) -> Image.Image:
    """从 alpha 通道生成一层阴影 bitmap，加 blur + offset。"""
    if rgba.mode != "RGBA":
        rgba = rgba.convert("RGBA")
    alpha = rgba.split()[-1]
    shadow = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, opacity), mask=alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_px))
    # canvas 比商品大一点，给 offset 腾空间
    pad_x = abs(offset[0]) + blur_px * 2
    pad_y = abs(offset[1]) + blur_px * 2
    out = Image.new("RGBA", (rgba.size[0] + pad_x * 2, rgba.size[1] + pad_y * 2), (0, 0, 0, 0))
    out.paste(shadow, (pad_x + offset[0], pad_y + offset[1]))
    return out, pad_x, pad_y


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

    # Composite: bg → 远投影 (软, 模拟环境光) → 接触阴影 (硬, 模拟商品压在桌面) → cutout
    canvas = bg.convert("RGBA")
    if drop_shadow:
        # 远投影：偏移多、模糊大、不透明度低 — 商品远处的环境投影
        far_shadow, pad_fx, pad_fy = _make_shadow_layer(
            cut_resized, blur_px=22, opacity=55, offset=(2, 28),
        )
        canvas.alpha_composite(far_shadow, (x - pad_fx, y - pad_fy))
        # 接触阴影：偏移很小、模糊小、不透明度高 — 商品底部和桌面贴合处
        contact_shadow, pad_cx, pad_cy = _make_shadow_layer(
            cut_resized, blur_px=4, opacity=140, offset=(0, 5),
        )
        canvas.alpha_composite(contact_shadow, (x - pad_cx, y - pad_cy))
    canvas.alpha_composite(cut_resized, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "JPEG", quality=92)
    return output_path


def _crop_to_cutout_bbox(rgba: Image.Image) -> Image.Image:
    """Tighten商品 to its visible alpha bounding box (drop transparent padding)."""
    bbox = rgba.split()[-1].getbbox()
    return rgba.crop(bbox) if bbox else rgba
