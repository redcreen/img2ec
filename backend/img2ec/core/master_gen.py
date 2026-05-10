"""调用 ComfyUI 生成 master 图（Phase 1 MVP：1x1；Phase 2：5 个 ratio）。

Phase 2 扩展为 generate_all_masters() 同时生 5 张 (1:1, long, 3:4, 9:16, 16:9)。
"""
import tempfile
from pathlib import Path

from PIL import Image

from img2ec.infra.comfy_client import ComfyClient, ComfyError

# Master key → workflow file name (under backend/workflows/)
MASTER_WORKFLOW_FILES: dict[str, str] = {
    "1x1": "generate_master_1x1.json",
    "long": "generate_master_long.json",
    "3x4": "generate_master_3x4.json",
    "9x16": "generate_master_9x16.json",
    "16x9": "generate_master_16x9.json",
}


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


def _collect_output_images(history: dict) -> list[dict]:
    out: list[dict] = []
    for node_outputs in history.get("outputs", {}).values():
        out.extend(node_outputs.get("images", []))
    return out


def _generate_one(
    *,
    client: ComfyClient,
    workflow_path: Path,
    uploaded_cutout: str,
    prompt: str,
    negative_prompt: str,
    ip_weight: int,
    seed: int,
    output_path: Path,
) -> Path:
    """生成一张 master，使用已上传的 cutout 文件名。

    Args:
        client: ComfyClient 实例
        workflow_path: 本地 workflow JSON 路径
        uploaded_cutout: ComfyUI 上已上传的 cutout 文件名（字符串，非 Path）
        prompt: 正向提示词
        negative_prompt: 负向提示词
        ip_weight: IPAdapter 权重 (0-100)
        seed: 随机种子
        output_path: 输出文件路径

    Returns:
        output_path
    """
    # SceneTemplate.ip_adapter_weight is 0-100 (UX-friendly slider). IPAdapter Flux node
    # expects 0.0-1.0 float — convert here.
    workflow = client.render_workflow(
        workflow_path,
        cutout=uploaded_cutout,
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


def generate_all_masters(
    *,
    client: ComfyClient,
    workflows_dir: Path,
    cutout_path: Path,
    prompt: str,
    negative_prompt: str,
    ip_weight: int,
    seed: int,
    out_dir: Path,
    image_stem: str,
) -> dict[str, Path]:
    """生成 5 张 master 图（不同 aspect ratio），返回 {master_key: path}。

    关键优化：上传 cutout 一次，5 个 workflow 共用同一个已上传文件名，
    节省上传时间且复用同一个图到多个 workflow。

    Args:
        client: ComfyClient 实例
        workflows_dir: 包含 5 个 workflow JSON 文件的目录
        cutout_path: 原始 cutout 图路径（RGBA or RGB）
        prompt: 正向提示词
        negative_prompt: 负向提示词
        ip_weight: IPAdapter 权重 (0-100)
        seed: 基础随机种子（每个 ratio 稍微变种）
        out_dir: 输出 master 图的目录
        image_stem: 输出文件名前缀 (e.g., "front")

    Returns:
        {master_key: Path} 字典，其中 master_key in ("1x1", "long", "3x4", "9x16", "16x9")
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 一次性平坦化 + 上传，5 个 workflow 共用
    flat_cutout = _flatten_rgba_to_white_rgb(cutout_path)
    uploaded_name = client.upload_image(flat_cutout)

    paths: dict[str, Path] = {}
    for key, fname in MASTER_WORKFLOW_FILES.items():
        wf_path = workflows_dir / fname
        out_path = out_dir / f"{image_stem}-{key}.jpg"
        _generate_one(
            client=client,
            workflow_path=wf_path,
            uploaded_cutout=uploaded_name,
            prompt=prompt,
            negative_prompt=negative_prompt,
            ip_weight=ip_weight,
            seed=seed + hash(key) % 1000,  # 不同 ratio 用稍变种子，避免 5 张视觉过于一致
            output_path=out_path,
        )
        paths[key] = out_path
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
    """跑 ComfyUI 生 1 张 1:1 master，存到 output_path。

    Deprecated: Phase 1 backward-compat entry point. Use generate_all_masters for Phase 2+.
    """
    flat_cutout = _flatten_rgba_to_white_rgb(cutout_path)
    uploaded_name = client.upload_image(flat_cutout)
    return _generate_one(
        client=client,
        workflow_path=workflow_path,
        uploaded_cutout=uploaded_name,
        prompt=prompt,
        negative_prompt=negative_prompt,
        ip_weight=ip_weight,
        seed=seed,
        output_path=output_path,
    )
