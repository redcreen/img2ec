"""调用 ComfyUI 生成 1 张 master（Phase 1 MVP：仅 1:1）。

Phase 2 扩展为 generate_masters_all() 同时生 5 张 (1:1, long, 3:4, 9:16, 16:9)。
"""
import tempfile
from pathlib import Path

from PIL import Image

from img2ec.infra.comfy_client import ComfyClient, ComfyError


def _flatten_rgba_to_white_rgb(src: Path) -> Path:
    """If src is RGBA (transparent cutout), composite onto white and save as RGB JPEG.

    IPAdapter Flux extracts visual features via siglip CLIP-vision; transparent regions
    confuse the embedding. Compositing on white gives IPAdapter a clean 商品-on-white reference.
    Returns path to the flattened temp file (or the original path if no conversion needed).
    """
    with Image.open(src) as img:
        if img.mode != "RGBA":
            return src
        white = Image.new("RGBA", img.size, (255, 255, 255, 255))
        composed = Image.alpha_composite(white, img).convert("RGB")
    tmp = Path(tempfile.gettempdir()) / f"ipadapter_input_{src.stem}.jpg"
    composed.save(tmp, "JPEG", quality=92)
    return tmp


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
    """跑 ComfyUI 生 1 张 1:1 master，存到 output_path。"""
    flat_cutout = _flatten_rgba_to_white_rgb(cutout_path)
    uploaded_name = client.upload_image(flat_cutout)
    # SceneTemplate.ip_adapter_weight is 0-100 (UX-friendly slider). IPAdapter Flux node
    # expects 0.0-1.0 float — convert here.
    workflow = client.render_workflow(
        workflow_path,
        cutout=uploaded_name,
        prompt=prompt,
        neg=negative_prompt,
        ip_weight=ip_weight / 100.0,
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


def _collect_output_images(history: dict) -> list[dict]:
    out: list[dict] = []
    for node_outputs in history.get("outputs", {}).values():
        out.extend(node_outputs.get("images", []))
    return out
