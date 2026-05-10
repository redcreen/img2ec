"""Pillow renderers for detail-page modules.

Each render_* function accepts (config: dict, ctx: dict) and returns an RGBA Image
of width = config["canvas_width"] and computed height. The composer concatenates
multiple module outputs vertically into a long detail-page image.

Available context fields (provided by composer):
    canvas_width: int
    fonts: dict[str, dict[int, ImageFont]] — by weight then size
    copy: dict — LLM-generated platform copy (title, subtitle, selling_points, ...)
    images: dict[str, Path] — keyed by master_key (1x1, long, etc.)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

ModuleRenderer = Callable[[dict, dict], Image.Image]


def _font(ctx: dict, weight: str, size: int) -> ImageFont.FreeTypeFont:
    weight_map = ctx["fonts"][weight]
    if size not in weight_map:
        weight_map[size] = ImageFont.truetype(str(ctx["font_paths"][weight]), size=size)
    return weight_map[size]


def render_hero(config: dict, ctx: dict) -> Image.Image:
    """Top hero block: 1x1 master image with brand-color background padding."""
    w = ctx["canvas_width"]
    h = config.get("height", 800)
    bg_color = tuple(config.get("bg_color", [248, 244, 238]))
    canvas = Image.new("RGBA", (w, h), bg_color + (255,))
    img_path = ctx["images"].get("1x1")
    if img_path:
        with Image.open(img_path) as src:
            src_rgb = src.convert("RGB")
            target = int(min(w, h) * config.get("scale", 0.78))
            src_rgb = _fit_square(src_rgb, target)
            x = (w - target) // 2
            y = (h - target) // 2
            canvas.paste(src_rgb, (x, y))
    return canvas


def render_title_banner(config: dict, ctx: dict) -> Image.Image:
    """Title + subtitle on solid background."""
    w = ctx["canvas_width"]
    h = config.get("height", 280)
    bg_color = tuple(config.get("bg_color", [255, 255, 255]))
    text_color = tuple(config.get("text_color", [30, 30, 30]))
    sub_color = tuple(config.get("subtitle_color", [120, 120, 120]))

    canvas = Image.new("RGBA", (w, h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)
    title = (ctx["copy"].get("title") or "").strip()
    subtitle = (ctx["copy"].get("subtitle") or "").strip()
    title_font = _font(ctx, "Bold", config.get("title_size", 40))
    sub_font = _font(ctx, "Regular", config.get("subtitle_size", 22))

    title_lines = _wrap(title, title_font, w - 80)
    sub_lines = _wrap(subtitle, sub_font, w - 80) if subtitle else []

    title_block_h = len(title_lines) * (config.get("title_size", 40) + 8)
    sub_block_h = len(sub_lines) * (config.get("subtitle_size", 22) + 6) + (24 if sub_lines else 0)
    total_h = title_block_h + sub_block_h
    y = (h - total_h) // 2

    for line in title_lines:
        draw.text((w // 2, y), line, font=title_font, fill=text_color, anchor="mt")
        y += config.get("title_size", 40) + 8
    if sub_lines:
        y += 16
        for line in sub_lines:
            draw.text((w // 2, y), line, font=sub_font, fill=sub_color, anchor="mt")
            y += config.get("subtitle_size", 22) + 6
    return canvas


def render_selling_points(config: dict, ctx: dict) -> Image.Image:
    """3-column grid of selling points (icon stub + title + body)."""
    w = ctx["canvas_width"]
    h = config.get("height", 360)
    bg_color = tuple(config.get("bg_color", [248, 244, 238]))
    card_color = tuple(config.get("card_color", [255, 255, 255]))
    text_color = tuple(config.get("text_color", [30, 30, 30]))
    accent = tuple(config.get("accent_color", [191, 130, 60]))

    canvas = Image.new("RGBA", (w, h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)
    points = (ctx["copy"].get("selling_points") or [])[: config.get("max_points", 3)]
    if not points:
        return canvas

    pad = 24
    gap = 16
    cards_total = w - pad * 2
    card_w = (cards_total - gap * (len(points) - 1)) // len(points)
    card_h = h - pad * 2
    head_font = _font(ctx, "Bold", 22)
    body_font = _font(ctx, "Regular", 16)

    for idx, point in enumerate(points):
        x = pad + idx * (card_w + gap)
        y = pad
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=12, fill=card_color + (255,))
        # Accent dot
        draw.ellipse([x + card_w // 2 - 12, y + 24, x + card_w // 2 + 12, y + 48], fill=accent + (255,))
        # Title (first 8 chars as headline)
        head_text = point[:10] + ("…" if len(point) > 10 else "")
        draw.text((x + card_w // 2, y + 70), head_text, font=head_font, fill=text_color, anchor="mt")
        # Body (wrapped full point)
        body_lines = _wrap(point, body_font, card_w - 24)
        ty = y + 110
        for line in body_lines[:4]:
            draw.text((x + card_w // 2, ty), line, font=body_font, fill=text_color, anchor="mt")
            ty += 22

    return canvas


def render_full_image(config: dict, ctx: dict) -> Image.Image:
    """Full-width long master image."""
    w = ctx["canvas_width"]
    img_path = ctx["images"].get("long") or ctx["images"].get("1x1")
    if img_path is None:
        return Image.new("RGBA", (w, 600), (255, 255, 255, 255))
    with Image.open(img_path) as src:
        src_rgb = src.convert("RGB")
        ratio = w / src_rgb.size[0]
        new_h = int(src_rgb.size[1] * ratio)
        resized = src_rgb.resize((w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, new_h), (255, 255, 255, 255))
    canvas.paste(resized, (0, 0))
    return canvas


def render_cta(config: dict, ctx: dict) -> Image.Image:
    """Call-to-action footer (button-like block)."""
    w = ctx["canvas_width"]
    h = config.get("height", 200)
    bg_color = tuple(config.get("bg_color", [255, 255, 255]))
    btn_color = tuple(config.get("btn_color", [191, 130, 60]))
    btn_text = config.get("text", "立即购买")
    btn_text_color = tuple(config.get("btn_text_color", [255, 255, 255]))

    canvas = Image.new("RGBA", (w, h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)

    btn_w = int(w * 0.6)
    btn_h = 90
    bx = (w - btn_w) // 2
    by = (h - btn_h) // 2
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=btn_color + (255,))
    btn_font = _font(ctx, "Heavy", 30)
    draw.text((w // 2, by + btn_h // 2), btn_text, font=btn_font, fill=btn_text_color, anchor="mm")

    return canvas


# ---- helpers ----
def _fit_square(img: Image.Image, side: int) -> Image.Image:
    w, h = img.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    cropped = img.crop((left, top, left + s, top + s))
    return cropped.resize((side, side), Image.LANCZOS)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Greedy wrap by character (CJK-friendly; treats each char as breakable)."""
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        bbox = font.getbbox(trial)
        if bbox[2] <= max_w:
            current = trial
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


MODULE_RENDERERS: dict[str, ModuleRenderer] = {
    "hero": render_hero,
    "title_banner": render_title_banner,
    "selling_points": render_selling_points,
    "full_image": render_full_image,
    "cta": render_cta,
}
