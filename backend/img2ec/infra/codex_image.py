"""Codex CLI image generation backend.

Replaces ComfyUI Flux for scene background generation. Significantly higher quality
(real marble texture, real caustics) at similar latency (~30-60s/image).

Architecture:
- subprocess `codex exec` with image-generation prompt
- Codex saves PNG to ~/.codex/generated_images/<session>/ig_*.png
- We find the newest PNG after exec and copy/resize to target path
- Cost: charges against user's ChatGPT/OpenAI Codex subscription

Compared to ComfyUI Flux:
- ✓ Better visual quality (gpt-image-1 underneath vs Flux dev FP8)
- ✓ Better light realism (window caustics, soft shadows)
- ✓ Sharper textures (marble veining, fabric, wood grain)
- ✗ Slightly slower per call (Codex CLI overhead + cloud latency)
- ✗ Requires logged-in Codex CLI on the host running the backend
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image


CODEX_IMG_DIR = Path.home() / ".codex" / "generated_images"


class CodexImageError(RuntimeError):
    pass


def _fit_to_target(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Center-crop image to target aspect ratio, then resize.

    Preserves the商品 aspect — never stretches/squishes. Drops some pixels at
    the edges if input aspect doesn't match target.
    """
    target_w, target_h = target
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if abs(src_ratio - target_ratio) < 0.01:
        return img.resize(target, Image.LANCZOS)
    if src_ratio > target_ratio:
        # source 太宽，裁两边
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, src_h))
    else:
        # source 太高，裁上下
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        cropped = img.crop((0, top, src_w, top + new_h))
    return cropped.resize(target, Image.LANCZOS)


# Codex/gpt-image-1 supported native sizes — we ask in these so output isn't squished.
_PROMPT_SIZE_HINT: dict[str, str] = {
    # 比例图（带场景）
    "1x1":  "1024x1024",
    "long": "1024x1536",
    "3x4":  "1024x1536",
    "9x16": "1024x1792",
    "16x9": "1792x1024",
    # 特写图（白底，多角度）
    "front":  "1024x1024",
    "side":   "1024x1024",
    "detail": "1024x1024",
}

TARGET_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1x1":  (1024, 1024),
    "long": (1024, 1536),
    "3x4":  (1024, 1536),
    "9x16": (1024, 1792),
    "16x9": (1792, 1024),
    "front":  (1024, 1024),
    "side":   (1024, 1024),
    "detail": (1024, 1024),
}

# 特写图（角度图）：白底，无场景，对商品做不同视角。共用 build_master_prompt。
CLOSEUP_KEYS = {"front", "side", "detail"}


def _run_codex_to_image(
    *,
    full_prompt: str,
    input_image: Path | None,
    target_dims: tuple[int, int],
    output_path: Path,
    timeout: int,
    codex_bin: str,
) -> Path:
    """Shared subprocess machinery: run codex exec, find newest PNG, resize, save."""
    before_ts = time.time()
    cmd = [codex_bin, "exec", "-", "--ephemeral", "--skip-git-repo-check"]
    if input_image is not None:
        cmd.extend(["-i", str(input_image)])

    try:
        proc = subprocess.run(
            cmd,
            input=full_prompt.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise CodexImageError(f"codex exec timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise CodexImageError(f"codex binary not found: {codex_bin}") from e

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[-300:]
        raise CodexImageError(f"codex rc={proc.returncode}: {stderr}")

    if not CODEX_IMG_DIR.exists():
        raise CodexImageError(f"codex images dir does not exist: {CODEX_IMG_DIR}")
    candidates = [p for p in CODEX_IMG_DIR.rglob("*.png") if p.stat().st_mtime >= before_ts - 1]
    if not candidates:
        stdout_tail = proc.stdout.decode("utf-8", errors="replace")[-300:]
        raise CodexImageError(f"no new image produced. stdout tail: {stdout_tail!r}")
    newest = max(candidates, key=lambda p: p.stat().st_mtime)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(newest) as src:
        rgb = src.convert("RGB")
        if rgb.size != target_dims:
            rgb = _fit_to_target(rgb, target_dims)
        rgb.save(output_path, "JPEG", quality=92)

    return output_path


def generate_background_image(
    *,
    prompt: str,
    ratio_key: str,
    output_path: Path,
    timeout: int = 240,
    codex_bin: str = "codex",
) -> Path:
    """Generate a scene-only background image (商品 to be PIL-composited later).

    [Path A composite mode — fallback only. Path C 'codex_native' direct img2img is preferred.]
    """
    size_hint = _PROMPT_SIZE_HINT.get(ratio_key, "1024x1024")
    target_dims = TARGET_DIMENSIONS.get(ratio_key)
    if target_dims is None:
        raise CodexImageError(f"unknown ratio_key: {ratio_key}")

    full_prompt = (
        f"Generate a single photographic image at {size_hint} resolution. "
        f"Subject: {prompt} "
        f"Constraints: empty scene with NO product, NO person, NO logo, NO text, NO watermark — "
        f"just the background ready for product placement; high resolution; sharp realistic detail."
    )
    return _run_codex_to_image(
        full_prompt=full_prompt,
        input_image=None,
        target_dims=target_dims,
        output_path=output_path,
        timeout=timeout,
        codex_bin=codex_bin,
    )


def generate_master_from_input(
    *,
    source_image: Path,
    scene_prompt: str,
    ratio_key: str,
    output_path: Path,
    timeout: int = 300,
    codex_bin: str = "codex",
    extra_prompt: str = "",
    extra_weight: float = 0.0,
) -> Path:
    """Path C — Codex 直接 image-to-image：商品 + 场景一步出图。

    输入用户原图（含杂背景），Codex 自己识别商品，把它放到 scene_prompt 描述的新场景里，
    保留商品所有细节同时生成自然光照、阴影、表面接触感。**不需要 rembg，不需要 PIL composite**。

    Args:
        source_image: 用户上传的原图（任意背景）
        scene_prompt: 目标场景描述（如 "中式实木桌面"）
        ratio_key: 1x1 / long / 3x4 / 9x16 / 16x9
        output_path: 输出 master 文件路径
    """
    target_dims = TARGET_DIMENSIONS.get(ratio_key)
    if target_dims is None:
        raise CodexImageError(f"unknown ratio_key: {ratio_key}")

    full_prompt = build_master_prompt(
        scene_prompt=scene_prompt, ratio_key=ratio_key,
        extra_prompt=extra_prompt, extra_weight=extra_weight,
    )
    return _run_codex_to_image(
        full_prompt=full_prompt,
        input_image=source_image,
        target_dims=target_dims,
        output_path=output_path,
        timeout=timeout,
        codex_bin=codex_bin,
    )


def generate_size_diagram(
    *,
    source_image: Path,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    output_path: Path,
    style: str = "white",  # "white" 纯白底；"template" 用 scene_prompt 描述的场景做背景
    scene_prompt: str | None = None,
    timeout: int = 300,
    codex_bin: str = "codex",
) -> Path:
    """Codex 直接生成尺寸示意图：商品本体 + 双向箭头标尺 + 中文尺寸标注。

    style="white"：纯白底（电商规格图标准）
    style="template"：用 scene_prompt 描述的场景做背景（与 SKU 主图风格一致）
    """
    if style == "template" and scene_prompt:
        bg_clause = (
            f"(1) background scene: {scene_prompt}. The product sits naturally on a believable surface "
            f"in this scene, with matched lighting and natural contact shadow"
        )
    else:
        bg_clause = (
            "(1) clean pure-white (#FFFFFF) background, NO scene, NO surface, NO context, only a soft "
            "natural contact shadow under the product (10-15% opacity gray)"
        )

    full_prompt = (
        f"Generate a single 1024x1024 e-commerce product size-specification diagram. "
        f"Use the input photo as the reference for the product's exact appearance — preserve "
        f"every shape, color, pattern and texture detail of the product itself. "
        f"\n\nLayout requirements: "
        f"{bg_clause}; "
        f"(2) the product is centered, occupying ~60% of frame width, fully visible with margin around it; "
        f"(3) below the product, draw a horizontal black double-headed arrow that spans the product's "
        f"width only (NOT the full canvas), with the label \"长 {_fmt_cm(length_cm)} cm\" centered "
        f"below it (large bold sans-serif Chinese font); "
        f"(4) to the right of the product, draw a vertical black double-headed arrow that spans the "
        f"product's height only (NOT the full canvas), with the label \"高 {_fmt_cm(height_cm)} cm\" "
        f"placed to the right of the arrow (rotated 90° if needed); "
        f"(5) in the bottom-right corner, smaller gray text \"宽 {_fmt_cm(width_cm)} cm（深度）\" "
        f"indicating depth; "
        f"(6) the arrows must measure the PRODUCT itself, not the full image frame — start and end "
        f"exactly at the product's left/right or top/bottom edges; "
        f"(7) absolutely NO additional product duplicates, NO logos, NO watermark, NO additional text "
        f"besides the dimension labels; "
        f"(8) the visual style must look like a professional Chinese e-commerce product specification "
        f"sheet — sharp lines, accurate measurements; the dimension annotation overlay is on top of the "
        f"chosen background."
    )
    return _run_codex_to_image(
        full_prompt=full_prompt,
        input_image=source_image,
        target_dims=(1024, 1024),
        output_path=output_path,
        timeout=timeout,
        codex_bin=codex_bin,
    )


def _fmt_cm(v: float) -> str:
    """整数显示无小数点；非整数保留 1 位小数。"""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


_CLOSEUP_DIRECTIVE: dict[str, str] = {
    "front": (
        "Capture the product straight-on from the FRONT view, head-on perspective, no rotation, "
        "the most recognizable face of the product directly facing the camera"
    ),
    "side": (
        "Capture the product from the SIDE view (rotated 90° from front), profile angle showing the "
        "depth and side silhouette of the product"
    ),
    "detail": (
        "Macro close-up shot — zoom in tight on the most distinctive textured area of the product "
        "(embroidery / fabric weave / pattern / craftsmanship detail). Fill the frame with the texture, "
        "showing fine surface detail and material quality"
    ),
}


def build_master_prompt(
    *,
    scene_prompt: str,
    ratio_key: str,
    extra_prompt: str = "",
    extra_weight: float = 0.0,
) -> str:
    """组装传给 Codex 的完整 prompt（前端 preview 用同一个函数）。

    - ratio_key ∈ {1x1, long, 3x4, 9x16, 16x9}: 把商品放进 scene_prompt 描述的场景里
    - ratio_key ∈ {front, side, detail}: 白底特写，忽略 scene_prompt
    - extra_prompt / extra_weight: 用户附加诉求，权重 0..1 控制强调程度
    """
    size_hint = _PROMPT_SIZE_HINT.get(ratio_key, "1024x1024")
    suffix = _format_extra(extra_prompt, extra_weight)

    if ratio_key in CLOSEUP_KEYS:
        directive = _CLOSEUP_DIRECTIVE[ratio_key]
        base = (
            f"Generate a single {size_hint} e-commerce product close-up photograph. "
            f"Use the input image as the exact reference for the product — preserve every shape, "
            f"color, pattern, embroidery, texture and material detail. "
            f"\n\nShot: {directive}. "
            f"\n\nRequirements: "
            f"(1) pure white (#FFFFFF) studio background, NO scene, NO surface texture, NO context; "
            f"(2) soft even studio lighting, subtle natural contact shadow only; "
            f"(3) the product is centered, sharp focus, fills appropriate fraction of frame for the shot; "
            f"(4) the product must look visually identical to the input (same colors / pattern / material); "
            f"(5) absolutely NO text, NO logo, NO watermark, NO duplicate products; "
            f"(6) output a single high-resolution {size_hint} photograph."
        )
        return base + suffix

    base = (
        f"Place this exact product (preserve every embroidery detail, every stitch, every color, "
        f"every texture — pixel-fidelity for the product itself) into a new {size_hint} scene. "
        f"\n\nScene: {scene_prompt}\n\n"
        f"Critical rules: "
        f"(1) the product itself must remain visually identical to the input — same shape, "
        f"same colors, same patterns, same orientation, same materials; "
        f"(2) ONLY the surrounding scene/background changes; "
        f"(3) match the lighting direction and color temperature between product and new scene "
        f"(natural shadow under product, ambient color reflections, contact shadow); "
        f"(4) place the product on a believable surface with natural perspective; "
        f"(5) absolutely NO text, NO watermark, NO additional duplicate products in the frame; "
        f"(6) output a single high-resolution {size_hint} photograph."
    )
    return base + suffix


def _format_extra(extra_prompt: str, weight: float) -> str:
    """把用户附加 prompt 按权重转成强调级别字符串，附加到 base prompt 后。"""
    txt = (extra_prompt or "").strip()
    if not txt:
        return ""
    w = max(0.0, min(1.0, float(weight or 0.0)))
    if w < 0.25:
        emphasis = "Light preference (apply if it does not conflict with the rules above)"
    elif w < 0.55:
        emphasis = "Moderate emphasis"
    elif w < 0.85:
        emphasis = "Strong emphasis"
    else:
        emphasis = "HARD CONSTRAINT (must satisfy)"
    return (
        f"\n\nAdditional user instruction ({emphasis}, weight={w:.2f}): {txt}"
    )


def codex_text(
    *,
    prompt: str,
    input_image: Path | None = None,
    timeout: int = 90,
    codex_bin: str = "codex",
) -> str:
    """Run Codex CLI in text-output mode (no image expected).
    Returns stdout text. Used for vision/describe + prompt-expansion endpoints."""
    cmd = [codex_bin, "exec", "-", "--ephemeral", "--skip-git-repo-check"]
    if input_image is not None:
        cmd.extend(["-i", str(input_image)])
    try:
        proc = subprocess.run(
            cmd, input=prompt.encode("utf-8"),
            capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise CodexImageError(f"codex exec timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise CodexImageError(f"codex binary not found: {codex_bin}") from e
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[-300:]
        raise CodexImageError(f"codex rc={proc.returncode}: {stderr}")
    return proc.stdout.decode("utf-8", errors="replace")
