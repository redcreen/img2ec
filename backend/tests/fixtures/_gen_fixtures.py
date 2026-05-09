"""运行一次生成测试用图片。"""
from pathlib import Path
import random
from PIL import Image, ImageDraw

HERE = Path(__file__).parent

# 1) 纯白底图：白色画布 + 中央灰色矩形（"商品"）
img = Image.new("RGB", (800, 800), (255, 255, 255))
ImageDraw.Draw(img).rectangle([200, 200, 600, 600], fill=(120, 120, 120))
img.save(HERE / "white_bg.jpg", quality=92)

# 2) 拍照背景：杂色噪点
img = Image.new("RGB", (800, 800), (180, 160, 140))
px = img.load()
random.seed(42)
for x in range(800):
    for y in range(800):
        r, g, b = px[x, y]
        n = random.randint(-40, 40)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
ImageDraw.Draw(img).rectangle([200, 200, 600, 600], fill=(80, 80, 80))
img.save(HERE / "photo_bg.jpg", quality=92)
