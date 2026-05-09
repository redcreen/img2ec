"""白底检测：抽样 4 边的边缘像素，判断方差与亮度。

判定规则：
  · 边缘像素均值 RGB 都 > 240（接近白）
  · 边缘像素方差 < 阈值（颜色一致）
"""
from pathlib import Path

from PIL import Image

EDGE_BRIGHTNESS_MIN = 240
EDGE_VARIANCE_MAX = 200.0
EDGE_BAND_PX = 20


def is_white_background(img_path: Path | str) -> bool:
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    band = EDGE_BAND_PX

    # 取四边的像素带
    top = img.crop((0, 0, w, band))
    bottom = img.crop((0, h - band, w, h))
    left = img.crop((0, 0, band, h))
    right = img.crop((w - band, 0, w, h))

    pixels: list[tuple[int, int, int]] = []
    for region in (top, bottom, left, right):
        pixels.extend(region.getdata())

    n = len(pixels)
    if n == 0:
        return False

    sum_r = sum(p[0] for p in pixels)
    sum_g = sum(p[1] for p in pixels)
    sum_b = sum(p[2] for p in pixels)
    mean_r, mean_g, mean_b = sum_r / n, sum_g / n, sum_b / n

    if mean_r < EDGE_BRIGHTNESS_MIN or mean_g < EDGE_BRIGHTNESS_MIN or mean_b < EDGE_BRIGHTNESS_MIN:
        return False

    var = sum((p[0] - mean_r) ** 2 + (p[1] - mean_g) ** 2 + (p[2] - mean_b) ** 2 for p in pixels) / n
    return var < EDGE_VARIANCE_MAX
