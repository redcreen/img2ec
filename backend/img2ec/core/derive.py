"""Phase 2: 5 master → 15 platform-specific outputs via Pillow.

每个平台需要的尺寸都从对应 master 裁剪/缩放/补白派生。同 aspect ratio 跨平台共用一张
master，省 67% GPU 推理时间（vs 朴素 1 master/平台/尺寸）。
"""
from pathlib import Path

from PIL import Image

MASTER_KEYS = ["1x1", "long", "3x4", "9x16", "16x9"]

# 每平台需要的输出条目：name, target size (w,h), from which master
# size=None 表示用 master 原宽不缩放（仅用于 "long" 详情页：固定宽 750，高保持 master 比例）
PLATFORM_DERIVATIONS: dict[str, list[dict]] = {
    "douyin": [
        {"name": "main",       "size": (1080, 1080), "from": "1x1"},
        {"name": "detail-750", "size": None,         "from": "long"},
        {"name": "cover-3x4",  "size": (900, 1200),  "from": "3x4"},
        {"name": "cover-9x16", "size": (1080, 1920), "from": "9x16"},
    ],
    "shipinhao": [
        {"name": "main",       "size": (800, 800),   "from": "1x1"},
        {"name": "detail-750", "size": None,         "from": "long"},
        {"name": "cover-1x1",  "size": (800, 800),   "from": "1x1"},
        {"name": "cover-3x4",  "size": (900, 1200),  "from": "3x4"},
    ],
    "taobao": [
        {"name": "main",       "size": (800, 800),   "from": "1x1"},
        {"name": "detail-750", "size": None,         "from": "long"},
        {"name": "cover-16x9", "size": (1920, 1080), "from": "16x9"},
        {"name": "cover-1x1",  "size": (800, 800),   "from": "1x1"},
    ],
    "xiaohongshu": [
        {"name": "note-1x1",   "size": (1080, 1080), "from": "1x1"},
        {"name": "note-3x4",   "size": (900, 1200),  "from": "3x4"},
        {"name": "long",       "size": None,         "from": "long"},
    ],
}


def _resize_to(img: Image.Image, target: tuple[int, int] | None, master_key: str) -> Image.Image:
    """如果 target=None，按 master 原宽 750 缩放（详情页长图）。否则 fit 到 target。"""
    if target is None and master_key == "long":
        # 750w 长图：保持原比例，宽缩到 750
        w, h = img.size
        new_h = int(h * (750 / w))
        return img.resize((750, new_h), Image.LANCZOS)
    if target is None:
        raise ValueError("size=None only valid for master_key='long'")
    # target 给的是目标 (w, h)；按其比例 center-crop master 后缩放
    target_w, target_h = target
    target_ratio = target_w / target_h
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    if abs(src_ratio - target_ratio) < 0.01:
        return img.resize(target, Image.LANCZOS)
    # crop to target ratio
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        cropped = img.crop((0, top, src_w, top + new_h))
    return cropped.resize(target, Image.LANCZOS)


def derive_all_for_image(
    master_paths: dict[str, Path],
    sku_outputs_root: Path,
    image_stem: str,
) -> dict[str, list[Path]]:
    """对一张原图的 5 张 master 派生为 15 个平台输出。

    Returns: {platform: [output_path, ...]}
    """
    sku_outputs_root.mkdir(parents=True, exist_ok=True)
    out: dict[str, list[Path]] = {}
    for platform, items in PLATFORM_DERIVATIONS.items():
        platform_dir = sku_outputs_root / platform
        platform_dir.mkdir(parents=True, exist_ok=True)
        out[platform] = []
        for item in items:
            master_key = item["from"]
            if master_key not in master_paths:
                raise ValueError(f"missing master '{master_key}' for {platform}/{item['name']}")
            with Image.open(master_paths[master_key]) as src:
                src_rgb = src.convert("RGB")
                derived = _resize_to(src_rgb, item["size"], master_key)
                if item["size"]:
                    suffix = f"-{item['size'][0]}x{item['size'][1]}"
                else:
                    suffix = "-750w"
                dst = platform_dir / f"{image_stem}-{item['name']}{suffix}.jpg"
                derived.save(dst, quality=90)
                out[platform].append(dst)
    return out


# 向后兼容 Phase 1 入口（pipeline 还在用）。Task 4 后会移除调用方。
PLATFORMS_1X1_SIZES: dict[str, tuple[int, int]] = {
    "douyin": (1080, 1080),
    "shipinhao": (800, 800),
    "taobao": (800, 800),
    "xiaohongshu": (1080, 1080),
}


def derive_main_1x1_for_platforms(master_path: Path, sku_outputs_root: Path, image_stem: str) -> dict[str, Path]:
    """Deprecated Phase 1 entry. Use derive_all_for_image."""
    return {p: paths[0] for p, paths in derive_all_for_image(
        {"1x1": master_path},
        sku_outputs_root,
        image_stem,
    ).items() if paths}
