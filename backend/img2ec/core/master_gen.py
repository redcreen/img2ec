"""Generate master images: 5 ratios via Codex image-to-image.

Path C architecture (default): Codex/gpt-image-1 takes the user's source photo +
a scene description and outputs the商品 placed in the new scene with natural
lighting, shadow, and material match. **No rembg, no PIL composite step.**

Path A (fallback for `use_codex=False`): ComfyUI Flux generates background only,
PIL composites cutout on top. Kept for environments without Codex CLI.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from img2ec.core.composite import composite_cutout_on_background
from img2ec.core.cutout import cutout_with_rembg
from img2ec.infra.codex_image import (
    CodexImageError,
    generate_background_image,
    generate_master_from_input,
)
from img2ec.infra.comfy_client import ComfyClient, ComfyError

# Master key → workflow file name (under backend/workflows/)
# 仅 Path A (ComfyUI) 用 workflow 文件。Path C (Codex) 不用，但保持 keys 列表一致。
MASTER_WORKFLOW_FILES: dict[str, str] = {
    "1x1": "generate_master_1x1.json",
    "long": "generate_master_long.json",
    "3x4": "generate_master_3x4.json",
    "9x16": "generate_master_9x16.json",
    "16x9": "generate_master_16x9.json",
    "front":  "generate_master_1x1.json",   # 特写：与 1x1 同尺寸 workflow 复用
    "side":   "generate_master_1x1.json",
    "detail": "generate_master_1x1.json",
}


def _collect_output_images(history: dict) -> list[dict]:
    out: list[dict] = []
    for node_outputs in history.get("outputs", {}).values():
        out.extend(node_outputs.get("images", []))
    return out


def _next_version_path(out_dir: Path, image_stem: str, key: str) -> Path:
    """Pick next unused filename for this (image, ratio).
    First gen → <stem>-<key>.jpg; later regens → <stem>-<key>-v2.jpg, -v3.jpg, ..."""
    base = out_dir / f"{image_stem}-{key}.jpg"
    if not base.exists():
        return base
    v = 2
    while True:
        cand = out_dir / f"{image_stem}-{key}-v{v}.jpg"
        if not cand.exists():
            return cand
        v += 1


def _generate_background(
    *,
    client: ComfyClient,
    workflow_path: Path,
    prompt: str,
    negative_prompt: str,
    seed: int,
    output_path: Path,
) -> Path:
    """Submit prompt-only Flux workflow → download generated scene background."""
    workflow = client.render_workflow(
        workflow_path,
        prompt=prompt,
        neg=negative_prompt,
        seed=seed,
    )
    prompt_id = client.submit_prompt(workflow)
    history = client.wait_for_result(prompt_id)

    images = _collect_output_images(history)
    if not images:
        raise ComfyError(f"no output images for prompt {prompt_id}")
    img = images[0]
    client.download_output(
        filename=img["filename"],
        subfolder=img.get("subfolder", ""),
        type_=img.get("type", "output"),
        dst_path=output_path,
    )
    return output_path


def generate_all_masters(
    *,
    client: ComfyClient | None,
    workflows_dir: Path,
    source_image: Path,
    prompt: str,
    negative_prompt: str,
    ip_weight: int,
    seed: int,
    out_dir: Path,
    image_stem: str,
    use_codex: bool = True,
    on_master_done: "callable | None" = None,
    ratios: "list[str] | None" = None,
    extra_prompt: str = "",
    extra_weight: float = 0.0,
) -> dict[str, Path]:
    """Codex image-to-image 出 master。`ratios` 限定生成哪些尺寸（None=全部 5 张）。"""
    del ip_weight, seed  # unused
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    all_items = list(MASTER_WORKFLOW_FILES.items())
    if ratios is not None:
        items = [(k, v) for k, v in all_items if k in set(ratios)]
    else:
        items = all_items
    total = len(items)

    # Path A 仍然要用 cutout，按需懒生成
    cutout_path: Path | None = None

    for idx, (key, fname) in enumerate(items):
        master_path = _next_version_path(out_dir, image_stem, key)

        if use_codex:
            # Path C：源图 + 场景 prompt → 一步出 master（含商品 + 场景 + 自然光照阴影）
            generate_master_from_input(
                source_image=source_image,
                scene_prompt=prompt,
                ratio_key=key,
                output_path=master_path,
                extra_prompt=extra_prompt,
                extra_weight=extra_weight,
            )
        else:
            # Path A fallback：抠图 + AI bg + PIL composite
            assert client is not None and workflows_dir is not None
            if cutout_path is None:
                cutout_path = source_image.parent.parent / "cutout" / f"{image_stem}.png"
                cutout_path.parent.mkdir(parents=True, exist_ok=True)
                cutout_with_rembg(source_image, cutout_path)
            bg_dir = Path(tempfile.gettempdir()) / f"img2ec_bg_{image_stem}"
            bg_dir.mkdir(parents=True, exist_ok=True)
            bg_path = bg_dir / f"{image_stem}-{key}-bg.jpg"
            _generate_background(
                client=client,
                workflow_path=workflows_dir / fname,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=hash((image_stem, key)) & 0x7FFFFFFF,
                output_path=bg_path,
            )
            composite_cutout_on_background(
                cutout_path=cutout_path,
                background_path=bg_path,
                output_path=master_path,
                ratio_key=key,
            )

        paths[key] = master_path
        if on_master_done is not None:
            on_master_done(key, master_path, idx + 1, total)

    return paths


def generate_master_1x1(
    *,
    client: ComfyClient,
    workflow_path: Path,
    cutout_path: Path,
    prompt: str,
    negative_prompt: str,
    ip_weight: int,
    seed: int,
    output_path: Path,
) -> Path:
    """Single 1:1 master entry point (backward-compat from Phase 1).

    AI-generate 1:1 background + composite商品 cutout. Preserved for callers that
    want a one-shot single ratio.
    """
    del ip_weight  # unused in Path A
    bg_path = Path(tempfile.gettempdir()) / f"img2ec_bg_1x1_{output_path.stem}.jpg"
    _generate_background(
        client=client,
        workflow_path=workflow_path,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        output_path=bg_path,
    )
    return composite_cutout_on_background(
        cutout_path=cutout_path,
        background_path=bg_path,
        output_path=output_path,
        ratio_key="1x1",
    )
