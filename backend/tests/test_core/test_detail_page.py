from pathlib import Path

import pytest
from PIL import Image

from img2ec.core.detail_page import render_detail_page
from img2ec.core.detail_template import DEFAULT_TEMPLATE

FONT_DIR = Path(__file__).parents[2] / "assets" / "fonts"
FONTS_AVAILABLE = (FONT_DIR / "SourceHanSansCN-Regular.otf").exists()


@pytest.mark.skipif(not FONTS_AVAILABLE, reason="fonts not downloaded")
def test_render_detail_page_produces_long_jpg(tmp_path):
    img_1x1 = Image.new("RGB", (1024, 1024), (180, 130, 80))
    p1 = tmp_path / "1x1.jpg"
    img_1x1.save(p1)
    img_long = Image.new("RGB", (750, 1500), (200, 220, 240))
    p2 = tmp_path / "long.jpg"
    img_long.save(p2)

    out = tmp_path / "detail.jpg"
    result = render_detail_page(
        template=DEFAULT_TEMPLATE,
        copy={
            "title": "蓝色刺绣老虎布艺摆件",
            "subtitle": "纯手工苏绣 一针一线",
            "selling_points": ["刺绣工艺细致 金线细密", "布艺天然亲肤 安全耐用", "桌面装饰百搭 复古风"],
        },
        images={"1x1": p1, "long": p2},
        output_path=out,
    )
    assert result == out
    assert out.exists()
    with Image.open(out) as img:
        assert img.size[0] == 750
        # 5 modules → cumulative height should be substantial
        assert img.size[1] > 2000


@pytest.mark.skipif(not FONTS_AVAILABLE, reason="fonts not downloaded")
def test_render_detail_page_handles_missing_subtitle(tmp_path):
    img = Image.new("RGB", (1024, 1024), (200, 200, 200))
    p = tmp_path / "1x1.jpg"; img.save(p)
    plong = tmp_path / "long.jpg"; img.save(plong)
    out = tmp_path / "detail.jpg"
    render_detail_page(
        template=DEFAULT_TEMPLATE,
        copy={"title": "test", "subtitle": "", "selling_points": ["a", "b", "c"]},
        images={"1x1": p, "long": plong},
        output_path=out,
    )
    assert out.exists()


def test_unknown_module_raises():
    with pytest.raises(ValueError, match="unknown module"):
        render_detail_page(
            template={"canvas_width": 750, "modules": [{"type": "xx"}]},
            copy={}, images={},
            output_path=Path("/tmp/x.jpg"),
        )
