"""从 master 派生平台尺寸。

Phase 1 MVP：只派生 4 平台的 1:1 主图。
Phase 2 扩展为完整 5 master + 15 派生。
"""
from pathlib import Path

from PIL import Image

from img2ec.infra.fs_layout import platform_dir, outputs_dir, VALID_PLATFORMS

PLATFORMS_1X1_SIZES: dict[str, tuple[int, int]] = {
    "douyin": (1080, 1080),
    "shipinhao": (800, 800),
    "taobao": (800, 800),
    "xiaohongshu": (1080, 1080),
}


def _center_crop_to_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def derive_main_1x1_for_platforms(
    master_path: Path,
    sku_outputs_root: Path,
    image_stem: str,
) -> dict[str, Path]:
    """对每平台输出主图。返回 {platform: dst_path} 映射。"""
    sku_outputs_root.mkdir(parents=True, exist_ok=True)
    with Image.open(master_path) as src:
        src_rgb = src.convert("RGB")
        square = _center_crop_to_square(src_rgb) if src_rgb.size[0] != src_rgb.size[1] else src_rgb

        out_paths: dict[str, Path] = {}
        for platform, size in PLATFORMS_1X1_SIZES.items():
            target_dir = sku_outputs_root / platform
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / f"{image_stem}-main-{size[0]}x{size[1]}.jpg"
            resized = square.resize(size, Image.LANCZOS)
            resized.save(dst, quality=90)
            out_paths[platform] = dst

    return out_paths
