"""单张原图的处理流水线（同步函数；Celery task 包它）。

Phase 1 MVP：bg_detect → (cutout if needed) → master_gen 1:1 → derive 4 平台
"""
from pathlib import Path
from typing import Callable

from img2ec.core.bg_detect import is_white_background
from img2ec.core.cutout import cutout_with_rembg
from img2ec.core.derive import derive_main_1x1_for_platforms
from img2ec.core.master_gen import generate_master_1x1
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
    workflow_path: Path,
    on_progress: ProgressCb | None = None,
) -> dict[str, Path]:
    """跑完返回派生输出 {platform: path} 字典。"""
    cb: ProgressCb = on_progress or (lambda _s, _p: None)

    # 阶段 1: 抠图
    if is_white_background(src_path):
        cutout_path = src_path  # 白底直接拿原图当 cutout
    else:
        cb("cutting", 0)
        cutout_path = cutout_dir(sku_dir) / f"{image_stem}.png"
        cutout_with_rembg(src_path, cutout_path)
        cb("cutting", 100)

    # 阶段 2: 生 master
    cb("generating", 0)
    master_path = master_dir(sku_dir) / f"{image_stem}-1x1.jpg"
    generate_master_1x1(
        client=comfy_client,
        workflow_path=workflow_path,
        cutout_path=cutout_path,
        prompt=scene_prompt,
        negative_prompt=scene_neg,
        ip_weight=ip_weight,
        seed=seed,
        output_path=master_path,
    )
    cb("generating", 100)

    # 阶段 3: 派生
    cb("composing", 0)
    derived = derive_main_1x1_for_platforms(
        master_path=master_path,
        sku_outputs_root=outputs_dir(sku_dir),
        image_stem=image_stem,
    )
    cb("composing", 100)

    return derived
