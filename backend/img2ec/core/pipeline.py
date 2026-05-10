"""Phase 2: 5 master + 15 derived 完整 pipeline。"""
from pathlib import Path
from typing import Callable

from img2ec.core.bg_detect import is_white_background
from img2ec.core.cutout import cutout_with_rembg
from img2ec.core.derive import derive_all_for_image
from img2ec.core.master_gen import generate_all_masters
from img2ec.infra.comfy_client import ComfyClient
from img2ec.infra.fs_layout import cutout_dir, master_dir, outputs_dir

ProgressCb = Callable[[str, int], None]


def process_one_image(
    *,
    src_path: Path,
    sku_dir: Path,
    image_stem: str,
    scene_prompt: str,
    scene_neg: str,
    ip_weight: int,
    seed: int,
    comfy_client: ComfyClient,
    workflows_dir: Path,
    on_progress: ProgressCb | None = None,
) -> dict[str, list[Path]]:
    """跑完返回派生输出 {platform: [paths]} 字典。"""
    cb: ProgressCb = on_progress or (lambda _s, _p: None)

    # 阶段 1: 抠图
    if is_white_background(src_path):
        cutout_path = src_path
    else:
        cb("cutting", 0)
        cutout_path = cutout_dir(sku_dir) / f"{image_stem}.png"
        cutout_with_rembg(src_path, cutout_path)
        cb("cutting", 100)

    # 阶段 2: 生 5 张 master
    cb("generating", 0)
    master_paths = generate_all_masters(
        client=comfy_client,
        workflows_dir=workflows_dir,
        cutout_path=cutout_path,
        prompt=scene_prompt,
        negative_prompt=scene_neg,
        ip_weight=ip_weight,
        seed=seed,
        out_dir=master_dir(sku_dir),
        image_stem=image_stem,
    )
    cb("generating", 100)

    # 阶段 3: 派生
    cb("composing", 0)
    derived = derive_all_for_image(
        master_paths=master_paths,
        sku_outputs_root=outputs_dir(sku_dir),
        image_stem=image_stem,
    )
    cb("composing", 100)

    return derived
