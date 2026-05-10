from pathlib import Path

import pytest
from PIL import Image, ImageFont

from img2ec.core.detail_modules import MODULE_RENDERERS


FONT_DIR = Path(__file__).parents[2] / "assets" / "fonts"
FONTS_AVAILABLE = (FONT_DIR / "SourceHanSansCN-Regular.otf").exists()


@pytest.fixture
def ctx(tmp_path):
    if not FONTS_AVAILABLE:
        pytest.skip("fonts not downloaded")
    img = Image.new("RGB", (1024, 1024), (200, 100, 50))
    img_path = tmp_path / "1x1.jpg"
    img.save(img_path)
    long_img = Image.new("RGB", (750, 1500), (180, 200, 220))
    long_path = tmp_path / "long.jpg"
    long_img.save(long_path)

    font_paths = {w: FONT_DIR / f"SourceHanSansCN-{w}.otf" for w in ("Regular", "Bold", "Heavy")}
    return {
        "canvas_width": 750,
        "fonts": {"Regular": {}, "Bold": {}, "Heavy": {}},
        "font_paths": font_paths,
        "copy": {
            "title": "蓝色刺绣老虎布艺摆件",
            "subtitle": "纯手工苏绣 一针一线",
            "selling_points": ["刺绣工艺细致", "布艺天然亲肤", "桌面装饰百搭"],
        },
        "images": {"1x1": img_path, "long": long_path},
    }


def test_hero_returns_rgba_with_correct_width(ctx):
    out = MODULE_RENDERERS["hero"]({"height": 800}, ctx)
    assert out.mode == "RGBA"
    assert out.size == (750, 800)


def test_title_banner_renders_text(ctx):
    out = MODULE_RENDERERS["title_banner"]({"height": 280}, ctx)
    assert out.size == (750, 280)


def test_selling_points_3_cards(ctx):
    out = MODULE_RENDERERS["selling_points"]({"height": 360}, ctx)
    assert out.size == (750, 360)


def test_full_image_preserves_aspect(ctx):
    out = MODULE_RENDERERS["full_image"]({}, ctx)
    assert out.size[0] == 750
    # long source is 750:1500 → resized 750:1500
    assert out.size[1] == 1500


def test_cta_renders_button(ctx):
    out = MODULE_RENDERERS["cta"]({"height": 200, "text": "立即购买"}, ctx)
    assert out.size == (750, 200)
