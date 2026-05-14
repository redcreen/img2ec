"""Codex CLI image generation business layer.

Architecture:
- codex_adapter.py: thin wrapper around codex-imagen skill (mockable)
- prompt_builder.py: pure prompt composition (pytest-friendly)
- this file: orchestration — pick output path, call adapter, retry on refusal,
  resize/save, closeup PIL crop, size-diagram, etc.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from img2ec.infra.codex_adapter import AdapterError, generate_image
from img2ec.infra.prompt_builder import (
    CLOSEUP_KEYS,
    PROMPT_SIZE_HINT,
    TARGET_DIMENSIONS,
    build_master_prompt,
)


# 兼容旧代码引用
__all__ = [
    "CodexImageError", "CLOSEUP_KEYS", "PROMPT_SIZE_HINT", "TARGET_DIMENSIONS",
    "build_master_prompt", "codex_text", "generate_background_image",
    "generate_closeup_crop", "generate_master_from_input", "generate_size_diagram",
]


class CodexImageError(RuntimeError):
    """业务层统一错误（向后兼容名）。"""
    pass


def _fit_to_target(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Center-crop 到 target 比例，再 resize。保证不拉伸/挤压商品。"""
    target_w, target_h = target
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if abs(src_ratio - target_ratio) < 0.01:
        return img.resize(target, Image.LANCZOS)
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        cropped = img.crop((0, top, src_w, top + new_h))
    return cropped.resize(target, Image.LANCZOS)


def _run_codex_to_image(
    *,
    full_prompt: str,
    input_image: Path | None,
    target_dims: tuple[int, int],
    output_path: Path,
    timeout: int,
    codex_bin: str = "codex",  # legacy, ignored
    max_retries: int = 2,
) -> Path:
    """Run codex via adapter, retry on stochastic refusal, save as JPEG."""
    refs = [input_image] if input_image is not None else None
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        with tempfile.TemporaryDirectory(prefix="img2ec-codex-stage-") as td:
            raw_png = Path(td) / "raw.png"
            try:
                generate_image(full_prompt, raw_png, refs=refs, timeout_sec=timeout)
            except AdapterError as e:
                last_err = e
                if e.refusal and attempt < max_retries:
                    continue
                raise CodexImageError(str(e)) from e

            with Image.open(raw_png) as src:
                rgb = src.convert("RGB")
                if rgb.size != target_dims:
                    rgb = _fit_to_target(rgb, target_dims)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                rgb.save(output_path, "JPEG", quality=92)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise CodexImageError(f"output file missing or empty after save: {output_path}")
            return output_path

    raise CodexImageError(str(last_err) if last_err else "unknown codex error")


def codex_text(
    *,
    prompt: str,
    input_image: Path | None = None,
    timeout: int = 90,
    codex_bin: str = "codex",  # legacy
) -> str:
    """Run codex exec for text output (vision describe / JSON extract).

    与 image gen 复用 codex CLI 但不要图。直接走 subprocess（短任务，不必走 adapter）。
    """
    import os
    import subprocess
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


def generate_background_image(
    *,
    prompt: str,
    ratio_key: str,
    output_path: Path,
    timeout: int = 600,
    codex_bin: str = "codex",
) -> Path:
    """Path A fallback: 无产品的场景背景图（用于后续 PIL composite）。"""
    size_hint = PROMPT_SIZE_HINT.get(ratio_key, "1024x1024")
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


def _source_to_white_bg(source_image: Path, cache_path: Path | None = None) -> Image.Image:
    """rembg 抠图 → 白底合成。cache_path 命中则即时返回。"""
    if cache_path and cache_path.exists():
        with Image.open(cache_path) as im:
            return im.convert("RGB").copy()
    from rembg import remove
    with Image.open(source_image) as src:
        rgba = remove(src.convert("RGBA"))
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    composed = Image.alpha_composite(bg, rgba).convert("RGB")
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        composed.save(cache_path, "JPEG", quality=92)
    return composed


def generate_closeup_crop(
    *,
    source_image: Path,
    ratio_key: str,
    output_path: Path,
    cutout_cache: Path | None = None,
) -> Path:
    """特写图 = 抠图去背景 → 白底 → 局部 crop + 放大。不调 Codex。"""
    if ratio_key not in CLOSEUP_KEYS:
        raise CodexImageError(f"not a closeup key: {ratio_key}")
    configs = {
        "front":  (0.70, 0.0, 0.0),
        "side":   (0.60, 0.18, 0.0),
        "detail": (0.35, 0.0, 0.08),
    }
    frac, ox, oy = configs[ratio_key]
    rgb = _source_to_white_bg(source_image, cutout_cache)
    W, H = rgb.size
    sz = int(min(W, H) * frac)
    cx = W // 2 + int(W * ox)
    cy = H // 2 + int(H * oy)
    left = max(0, min(W - sz, cx - sz // 2))
    top = max(0, min(H - sz, cy - sz // 2))
    cropped = rgb.crop((left, top, left + sz, top + sz))
    out = cropped.resize((1024, 1024), Image.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path, "JPEG", quality=92)
    return output_path


def generate_master_from_input(
    *,
    source_image: Path,
    scene_prompt: str,
    ratio_key: str,
    output_path: Path,
    timeout: int = 600,
    codex_bin: str = "codex",
    extra_prompt: str = "",
    extra_weight: float = 0.0,
    extra_negative_prompt: str = "",
) -> Path:
    """Path C — image-to-image：商品 + 场景一步出图。"""
    target_dims = TARGET_DIMENSIONS.get(ratio_key)
    if target_dims is None:
        raise CodexImageError(f"unknown ratio_key: {ratio_key}")
    full_prompt = build_master_prompt(
        scene_prompt=scene_prompt, ratio_key=ratio_key,
        extra_prompt=extra_prompt, extra_weight=extra_weight,
        extra_negative_prompt=extra_negative_prompt,
    )
    return _run_codex_to_image(
        full_prompt=full_prompt,
        input_image=source_image,
        target_dims=target_dims,
        output_path=output_path,
        timeout=timeout,
        codex_bin=codex_bin,
    )


def _fmt_cm(v: float) -> str:
    """123.45 → '12.3 cm' (1 dp); 整数则不带小数。"""
    if abs(v - round(v)) < 0.05:
        return f"{int(round(v))} cm"
    return f"{v:.1f} cm"


DIMENSION_STYLES = ("white", "template")


def generate_size_diagram(
    *,
    source_image: Path,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    output_path: Path,
    style: str = "white",
    scene_prompt: str | None = None,
    timeout: int = 600,
    codex_bin: str = "codex",
) -> Path:
    """Codex 直接生成尺寸示意图：商品 + 标注。"""
    if style not in DIMENSION_STYLES:
        raise CodexImageError(f"unknown style: {style}")
    target_dims = TARGET_DIMENSIONS["1x1"]
    L = _fmt_cm(length_cm); W = _fmt_cm(width_cm); H = _fmt_cm(height_cm)

    if style == "template" and scene_prompt:
        bg = (
            f"(1) background scene: {scene_prompt}. The product sits naturally on a believable surface "
            f"with soft contact shadow."
        )
    else:
        bg = "(1) pure white (#FFFFFF) studio background, soft even studio lighting, subtle contact shadow."

    full_prompt = (
        f"Generate a single 1024x1024 e-commerce size diagram image. "
        f"Use the input image as the exact reference for the product — preserve every detail. "
        f"{bg} "
        f"(2) the product is centered, occupying ~60% of the frame, with clear sharp focus; "
        f"(3) overlay clean black double-arrow rulers on three sides of the product: "
        f"length (左右) = {L}, width (前后/深度) = {W}, height (上下) = {H}; "
        f"(4) Chinese labels in clean sans-serif font, positioned just outside each arrow: "
        f"长 {L} | 宽 {W} | 高 {H}; "
        f"(5) the product itself must look visually identical to the input photo "
        f"(same colors / pattern / material / orientation); "
        f"(6) NO watermark, NO extra products, NO unrelated text; "
        f"(7) output a single high-resolution 1024x1024 photograph."
    )
    return _run_codex_to_image(
        full_prompt=full_prompt,
        input_image=source_image,
        target_dims=target_dims,
        output_path=output_path,
        timeout=timeout,
        codex_bin=codex_bin,
    )
