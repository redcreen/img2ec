"""Path C pipeline: Codex 直接 image-to-image 出 master，跳过 rembg + PIL composite。

简化的链路：
  source photo → Codex (input + scene prompt) → 5 master → Pillow 派生 → 15 platform outputs

之前 Path A 流程（rembg → cutout → AI bg → PIL paste 商品 + shadow）保留为 fallback。
"""
from pathlib import Path
from typing import Callable

from img2ec.core.derive import derive_all_for_image
from img2ec.core.master_gen import generate_all_masters
from img2ec.infra.comfy_client import ComfyClient
from img2ec.infra.fs_layout import master_dir, outputs_dir

ProgressCb = Callable[[str, int], None]
MasterDoneCb = Callable[[str, Path, int, int], None]  # (key, master_path, idx, total)


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
    on_master_done: MasterDoneCb | None = None,
    ratios: "list[str] | None" = None,
    extra_prompt: str = "",
    extra_weight: float = 0.0,
    extra_negative_prompt: str = "",
    overwrite: bool = False,
    reference_image: Path | None = None,
    use_builtin_prompt: bool = True,
) -> dict[str, list[Path]]:
    """跑完返回派生输出 {platform: [paths]} 字典。"""
    cb: ProgressCb = on_progress or (lambda _s, _p: None)

    # Path C：Codex 直接吃用户原图 + 场景 prompt 出 master，5 张依次生成
    cb("generating", 0)
    master_out = master_dir(sku_dir)

    def _on_master_done(key: str, master_path: Path, idx: int, total: int) -> None:
        cb("generating", int(idx * 100 / total))
        if on_master_done is not None:
            on_master_done(key, master_path, idx, total)

    master_paths = generate_all_masters(
        client=comfy_client,
        workflows_dir=workflows_dir,
        source_image=src_path,
        prompt=scene_prompt,
        negative_prompt=scene_neg,
        ip_weight=ip_weight,
        seed=seed,
        out_dir=master_out,
        image_stem=image_stem,
        on_master_done=_on_master_done,
        ratios=ratios,
        extra_prompt=extra_prompt,
        extra_weight=extra_weight,
        extra_negative_prompt=extra_negative_prompt,
        overwrite=overwrite,
        reference_image=reference_image,
        use_builtin_prompt=use_builtin_prompt,
    )

    # Pillow 派生 15 个平台尺寸（裁剪/缩放）
    cb("composing", 0)
    derived = derive_all_for_image(
        master_paths=master_paths,
        sku_outputs_root=outputs_dir(sku_dir),
        image_stem=image_stem,
    )
    cb("composing", 100)

    return derived
