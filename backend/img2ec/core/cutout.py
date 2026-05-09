"""rembg 抠图。模型首次调用时下载 (~150MB)，缓存在 ~/.u2net/。"""
from pathlib import Path

from PIL import Image
from rembg import remove


def cutout_with_rembg(src_path: Path | str, out_path: Path | str) -> None:
    """读取 src_path 的 RGB 图，rembg 去背景，保存为 RGBA PNG 到 out_path。"""
    src = Path(src_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as img:
        img_rgb = img.convert("RGB")

    cut = remove(img_rgb)  # 返回 PIL.Image RGBA
    cut.save(out, format="PNG")
