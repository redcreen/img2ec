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


# Codex/gpt-image-1 supports these size hints natively; we map our 5 master keys to them.
# The actual generated image will be resized to TARGET_DIMENSIONS for consistency with derive.py.
_PROMPT_SIZE_HINT: dict[str, str] = {
    "1x1":  "1024x1024",
    "long": "1024x1792",
    "3x4":  "1024x1536",
    "9x16": "1024x1792",
    "16x9": "1792x1024",
}

# Final dimensions we want each master at (matches existing master_gen behaviour).
TARGET_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1x1":  (1024, 1024),
    "long": (750, 2000),
    "3x4":  (900, 1200),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}


def generate_background_image(
    *,
    prompt: str,
    ratio_key: str,
    output_path: Path,
    timeout: int = 240,
    codex_bin: str = "codex",
) -> Path:
    """Generate a scene-only background image via Codex CLI.

    Args:
        prompt: scene description (positive). Will be wrapped to enforce "no product, no person".
        ratio_key: one of MASTER keys: 1x1, long, 3x4, 9x16, 16x9
        output_path: target file path (parent dir auto-created)
        timeout: subprocess timeout
        codex_bin: codex CLI binary name

    Returns: output_path on success.
    Raises: CodexImageError on any failure.
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

    before_ts = time.time()
    try:
        proc = subprocess.run(
            [codex_bin, "exec", "-", "--ephemeral", "--skip-git-repo-check"],
            input=full_prompt.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise CodexImageError(f"codex exec timed out after {timeout}s for {ratio_key}") from e
    except FileNotFoundError as e:
        raise CodexImageError(f"codex binary not found: {codex_bin}") from e

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[-300:]
        raise CodexImageError(f"codex rc={proc.returncode}: {stderr}")

    # Find newest PNG generated since `before_ts`
    if not CODEX_IMG_DIR.exists():
        raise CodexImageError(f"codex images dir does not exist: {CODEX_IMG_DIR}")
    candidates = [p for p in CODEX_IMG_DIR.rglob("*.png") if p.stat().st_mtime >= before_ts - 1]
    if not candidates:
        stdout_tail = proc.stdout.decode("utf-8", errors="replace")[-300:]
        raise CodexImageError(f"no new image produced. stdout tail: {stdout_tail!r}")
    newest = max(candidates, key=lambda p: p.stat().st_mtime)

    # Copy + resize to target dimensions
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(newest) as src:
        rgb = src.convert("RGB")
        if rgb.size != target_dims:
            rgb = rgb.resize(target_dims, Image.LANCZOS)
        rgb.save(output_path, "JPEG", quality=92)

    return output_path
