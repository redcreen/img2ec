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
# Master TARGET_DIMENSIONS must match (or be very close to) Codex native to avoid
# heavy crop. derive.py 派生时会按平台需求 crop/resize 出最终 750×N、1080×1920 等。
_PROMPT_SIZE_HINT: dict[str, str] = {
    "1x1":  "1024x1024",
    "long": "1024x1536",  # Codex 实际最常返回这个 portrait
    "3x4":  "1024x1536",
    "9x16": "1024x1792",
    "16x9": "1792x1024",
}

# Master 输出原生 = Codex 自然出图尺寸；不再硬塞到 750x2000 这种它不会出的形状。
# derive.py 后续 crop+resize 到平台需求（750w 长图、1080×1920 等）。
TARGET_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1x1":  (1024, 1024),
    "long": (1024, 1536),
    "3x4":  (1024, 1536),
    "9x16": (1024, 1792),
    "16x9": (1792, 1024),
}


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
    size_hint = _PROMPT_SIZE_HINT.get(ratio_key, "1024x1024")
    target_dims = TARGET_DIMENSIONS.get(ratio_key)
    if target_dims is None:
        raise CodexImageError(f"unknown ratio_key: {ratio_key}")

    full_prompt = (
        f"Place this exact product (preserve every embroidery detail, every stitch, every color, "
        f"every texture — pixel-fidelity for the product itself) into a new {size_hint} scene. "
        f"\n\nScene: {scene_prompt}\n\n"
        f"Critical rules: "
        f"(1) the product itself must remain visually identical to the input — same shape, "
        f"same colors, same patterns, same materials, same orientation; "
        f"(2) ONLY the surrounding scene/background changes; "
        f"(3) match the lighting direction and color temperature between product and new scene "
        f"(natural shadow under product, ambient color reflections, contact shadow); "
        f"(4) place the product on a believable surface with natural perspective; "
        f"(5) absolutely NO text, NO watermark, NO additional duplicate products in the frame; "
        f"(6) output a single high-resolution {size_hint} photograph."
    )
    return _run_codex_to_image(
        full_prompt=full_prompt,
        input_image=source_image,
        target_dims=target_dims,
        output_path=output_path,
        timeout=timeout,
        codex_bin=codex_bin,
    )
