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
    """3 卖点纵向堆叠（数字 + 完整卖点文字），自适应高度。
    旧版用 3 列卡片 + 截断"…"产生的丑陋首行；新版纵向，文字完整展示，每条占一行。"""
    w = ctx["canvas_width"]
    bg_color = tuple(config.get("bg_color", [248, 244, 238]))
    card_color = tuple(config.get("card_color", [255, 255, 255]))
    text_color = tuple(config.get("text_color", [40, 40, 40]))
    accent = tuple(config.get("accent_color", [191, 130, 60]))

    points = (ctx["copy"].get("selling_points") or [])[: config.get("max_points", 3)]
    if not points:
        return Image.new("RGBA", (w, 60), bg_color + (255,))

    pad_outer = 24       # 卡片外边距
    pad_card = 24        # 卡片内边距
    gap = 14             # 卡片间距
    badge_w = 56         # 左侧编号圆 + 间距
    body_size = config.get("body_size", 22)
    body_font = _font(ctx, "Regular", body_size)
    badge_font = _font(ctx, "Bold", 26)

    text_max_w = w - pad_outer * 2 - pad_card * 2 - badge_w
    line_h = body_size + 8

    # 先算每张卡的高
    card_layouts: list[tuple[list[str], int]] = []
    for point in points:
        lines = _wrap(point, body_font, text_max_w)
        card_h = max(72, pad_card * 2 + len(lines) * line_h)
        card_layouts.append((lines, card_h))

    total_h = pad_outer * 2 + sum(c[1] for c in card_layouts) + gap * (len(points) - 1)
    canvas = Image.new("RGBA", (w, total_h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)

    y = pad_outer
    for idx, (lines, card_h) in enumerate(card_layouts):
        x = pad_outer
        right = w - pad_outer
        bottom = y + card_h
        draw.rounded_rectangle([x, y, right, bottom], radius=14, fill=card_color + (255,))
        # 左侧带 accent 色的圆形编号
        cx, cy = x + pad_card + 18, y + pad_card + 18
        draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=accent + (255,))
        draw.text((cx, cy), str(idx + 1), font=badge_font, fill=(255, 255, 255), anchor="mm")
        # 文字（左对齐、纵向居中）
        text_x = x + pad_card + badge_w
        block_h = len(lines) * line_h
        ty = y + (card_h - block_h) // 2
        for line in lines:
            draw.text((text_x, ty), line, font=body_font, fill=text_color)
            ty += line_h
        y = bottom + gap

    return canvas


def render_full_image(config: dict, ctx: dict) -> Image.Image:
    """Full-width image (按 config._key 取，没有就退回 long → 1x1)。"""
    w = ctx["canvas_width"]
    chosen = config.get("_key")
    img_path = (
        ctx["images"].get(chosen) if chosen else None
    ) or ctx["images"].get("long") or ctx["images"].get("1x1")
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


def render_size_diagram(config: dict, ctx: dict) -> Image.Image:
    """尺寸图模块：把 dimension 图（白底）等比缩到详情页宽度，带可选标题。
    images["size_white"] 或 images["size_template"] 之一必须存在。"""
    w = ctx["canvas_width"]
    bg_color = tuple(config.get("bg_color", [255, 255, 255]))
    title_text = config.get("title", "商品尺寸")
    title_size = config.get("title_size", 26)
    title_pad = 18

    img_key = config.get("key", "size_white")
    img_path = ctx["images"].get(img_key) or ctx["images"].get("size_template") or ctx["images"].get("size_white")
    if img_path is None:
        return Image.new("RGBA", (w, 60), bg_color + (255,))

    with Image.open(img_path) as src:
        rgb = src.convert("RGB")
        ratio = w / rgb.size[0]
        new_h = int(rgb.size[1] * ratio)
        resized = rgb.resize((w, new_h), Image.LANCZOS)

    title_font = _font(ctx, "Bold", title_size)
    title_bbox = title_font.getbbox(title_text)
    title_h = (title_bbox[3] - title_bbox[1]) + title_pad * 2

    canvas = Image.new("RGBA", (w, new_h + title_h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.text((w // 2, title_pad), title_text, font=title_font, fill=(40, 40, 40), anchor="mt")
    canvas.paste(resized, (0, title_h))
    return canvas


def render_color_comparison(config: dict, ctx: dict) -> Image.Image:
    """多变体颜色对比块：横排列出每个变体的 1×1 master + 颜色名。
    ctx["variants"] = [{"color_name": str, "image_path": Path}, ...]
    < 2 个变体则不渲染（返回 1px 空 canvas）。
    """
    w = ctx["canvas_width"]
    variants = ctx.get("variants", [])
    bg_color = tuple(config.get("bg_color", [248, 244, 238]))
    text_color = tuple(config.get("text_color", [30, 30, 30]))
    label_text = config.get("title", "颜色选择")

    if len(variants) < 2:
        return Image.new("RGBA", (w, 1), bg_color + (255,))

    pad = 28
    gap = 14
    label_size = config.get("label_size", 22)
    title_size = config.get("title_size", 32)
    cols = min(len(variants), config.get("max_cols", 4))
    cell_w = (w - pad * 2 - gap * (cols - 1)) // cols
    img_h = cell_w
    label_h = label_size + 16
    rows = (len(variants) + cols - 1) // cols
    total_h = pad + (title_size + 16) + (img_h + label_h + gap) * rows - gap + pad

    canvas = Image.new("RGBA", (w, total_h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(ctx, "Bold", title_size)
    label_font = _font(ctx, "Bold", label_size)

    # 标题
    draw.text((w // 2, pad), label_text, font=title_font, fill=text_color, anchor="mt")

    y = pad + title_size + 16
    for i, v in enumerate(variants):
        col = i % cols
        row = i // cols
        x = pad + col * (cell_w + gap)
        cy = y + row * (img_h + label_h + gap)

        # 商品图（每变体的 1×1）
        img_path = v.get("image_path")
        if img_path:
            try:
                with Image.open(img_path) as src:
                    rgb = src.convert("RGB")
                    rgb_fit = _fit_square(rgb, cell_w)
                    canvas.paste(rgb_fit, (x, cy))
            except Exception:
                draw.rectangle([x, cy, x + cell_w, cy + img_h], fill=(220, 220, 220, 255))
        else:
            draw.rectangle([x, cy, x + cell_w, cy + img_h], fill=(220, 220, 220, 255))

        # 颜色名
        name = v.get("color_name", "")
        draw.text((x + cell_w // 2, cy + img_h + 8), name,
                  font=label_font, fill=text_color, anchor="mt")

    return canvas


MODULE_RENDERERS: dict[str, ModuleRenderer] = {
    "hero": render_hero,
    "title_banner": render_title_banner,
    "selling_points": render_selling_points,
    "full_image": render_full_image,
    "cta": render_cta,
    "size_diagram": render_size_diagram,
    "color_comparison": render_color_comparison,
}
