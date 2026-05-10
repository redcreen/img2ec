"""Smoke check: ensure fonts dir exists and font files are loadable."""
from pathlib import Path

import pytest
from PIL import ImageFont

FONT_DIR = Path(__file__).parents[2] / "assets" / "fonts"

WEIGHTS = ["Regular", "Bold", "Heavy"]


@pytest.mark.parametrize("weight", WEIGHTS)
def test_font_file_exists(weight):
    p = FONT_DIR / f"SourceHanSansCN-{weight}.otf"
    if not p.exists():
        pytest.skip(f"{p.name} not downloaded — run scripts/setup_fonts.sh")
    assert p.stat().st_size > 1_000_000, f"{p.name} suspiciously small"


@pytest.mark.parametrize("weight", WEIGHTS)
def test_font_loads_with_pillow(weight):
    p = FONT_DIR / f"SourceHanSansCN-{weight}.otf"
    if not p.exists():
        pytest.skip(f"{p.name} not downloaded")
    font = ImageFont.truetype(str(p), size=24)
    bbox = font.getbbox("测试中文 Test")
    assert bbox is not None
    assert bbox[2] > 0
