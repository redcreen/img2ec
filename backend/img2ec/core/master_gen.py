"""Generate master images: AI scene background + composite商品 cutout.

Path A architecture (Phase 2.1+): the AI generates only the scene background;
the商品 itself is preserved 100% from the user's cutout via PIL paste. This avoids
IPAdapter's style-transfer behavior (which regenerates商品 in unpredictable ways
and is unsuitable for e-commerce where商品 fidelity is required).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from img2ec.core.composite import composite_cutout_on_background
from img2ec.infra.comfy_client import ComfyClient, ComfyError

# Master key → workflow file name (under backend/workflows/)
MASTER_WORKFLOW_FILES: dict[str, str] = {
    "1x1": "generate_master_1x1.json",
    "long": "generate_master_long.json",
    "3x4": "generate_master_3x4.json",
    "9x16": "generate_master_9x16.json",
    "16x9": "generate_master_16x9.json",
}


def _collect_output_images(history: dict) -> list[dict]:
    out: list[dict] = []
    for node_outputs in history.get("outputs", {}).values():
        out.extend(node_outputs.get("images", []))
    return out


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
    client: ComfyClient,
    workflows_dir: Path,
    cutout_path: Path,
    prompt: str,
    negative_prompt: str,
    ip_weight: int,  # accepted for backward-compat; currently unused (kept for V1.1 stylized mode)
    seed: int,
    out_dir: Path,
    image_stem: str,
) -> dict[str, Path]:
    """For each ratio: AI-generate background + PIL-composite商品 cutout on top.

    Returns: {master_key: master_path} dict for the 5 ratios.
    The cutout is preserved 100% (no IPAdapter regeneration).
    """
    del ip_weight  # unused in Path A; kept for signature compat
    out_dir.mkdir(parents=True, exist_ok=True)
    bg_dir = Path(tempfile.gettempdir()) / f"img2ec_bg_{image_stem}_{seed}"
    bg_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for key, fname in MASTER_WORKFLOW_FILES.items():
        bg_path = bg_dir / f"{image_stem}-{key}-bg.jpg"
        master_path = out_dir / f"{image_stem}-{key}.jpg"

        _generate_background(
            client=client,
            workflow_path=workflows_dir / fname,
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed + hash(key) % 1000,
            output_path=bg_path,
        )

        composite_cutout_on_background(
            cutout_path=cutout_path,
            background_path=bg_path,
            output_path=master_path,
            ratio_key=key,
        )

        paths[key] = master_path

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
