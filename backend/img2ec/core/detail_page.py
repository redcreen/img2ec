"""Detail-page composer: stitch module outputs into a long detail-page image."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from img2ec.core.detail_modules import MODULE_RENDERERS

FONT_DIR = Path(__file__).parents[2] / "assets" / "fonts"


def _font_paths() -> dict[str, Path]:
    return {w: FONT_DIR / f"SourceHanSansCN-{w}.otf" for w in ("Regular", "Bold", "Heavy")}


def render_detail_page(
    *,
    template: dict,
    copy: dict,
    images: dict[str, Path],
    output_path: Path,
    variants: list[dict] | None = None,
) -> Path:
    """Render template → save as JPEG. Returns output_path.

    Args:
        variants: 可选，[{color_name, image_path}, ...]，给 color_comparison module 用
    """
    canvas_width = template.get("canvas_width", 750)
    ctx = {
        "canvas_width": canvas_width,
        "fonts": {"Regular": {}, "Bold": {}, "Heavy": {}},
        "font_paths": _font_paths(),
        "copy": copy,
        "images": images,
        "variants": variants or [],
    }

    rendered_blocks: list[Image.Image] = []
    for block in template.get("modules", []):
        renderer = MODULE_RENDERERS.get(block["type"])
        if renderer is None:
            raise ValueError(f"unknown module type: {block['type']}")
        rendered_blocks.append(renderer(block.get("config", {}), ctx))

    total_height = sum(b.size[1] for b in rendered_blocks)
    canvas = Image.new("RGB", (canvas_width, total_height), (255, 255, 255))
    y = 0
    for block in rendered_blocks:
        canvas.paste(block.convert("RGB"), (0, y))
        y += block.size[1]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, "JPEG", quality=90)
    return output_path
