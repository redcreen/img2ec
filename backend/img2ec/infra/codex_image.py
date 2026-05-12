"""Codex CLI image generation backend.

Replaces ComfyUI Flux for scene background generation. Significantly higher quality
(real marble texture, real caustics) at similar latency (~30-60s/image).

Architecture:
- subprocess `codex exec` with image-generation prompt
- Per-call isolated CODEX_HOME (symlinks auth/config from real ~/.codex/);
  generated images go to <isolated_home>/generated_images/<session>/ig_*.png
- We pick up the PNG from the isolated home → guarantees zero cross-task contamination
- Cost: charges against user's ChatGPT/OpenAI Codex subscription
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from PIL import Image


REAL_CODEX_HOME = Path.home() / ".codex"
CODEX_IMG_DIR = REAL_CODEX_HOME / "generated_images"  # 保留全局路径常量给可能的兼容场景

# 真实 CODEX_HOME 里调用 codex 所必需的文件（auth、配置、agent 上下文）。
# 用 symlink 暴露到隔离 home 里，让 codex 能正常认证/读 config。
_LINKED_FILES = ("auth.json", "config.toml", "AGENTS.md", "hooks.json")
_LINKED_DIRS  = ("bin",)


@contextmanager
def _isolated_codex_home():
    """每次 codex exec 用独立 CODEX_HOME（临时目录），auth/config 软链接过去。
    保证 generated_images 物理隔离，并发零冲突。"""
    real = REAL_CODEX_HOME
    with tempfile.TemporaryDirectory(prefix="img2ec-codex-") as td:
        tmp = Path(td)
        for name in _LINKED_FILES:
            src = real / name
            if src.exists():
                try: (tmp / name).symlink_to(src)
                except OSError: pass
        for name in _LINKED_DIRS:
            src = real / name
            if src.exists():
                try: (tmp / name).symlink_to(src, target_is_directory=True)
                except OSError: pass
        yield tmp


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
    """跑 codex exec → 在隔离 CODEX_HOME 里取唯一 PNG → resize 输出。

    并发零冲突：每次调用用 tempdir 当 CODEX_HOME，generated_images/ 是本次专属，
    任何其他进程/应用并发跑 Codex 都不影响。
    """
    with _isolated_codex_home() as home:
        cmd = [codex_bin, "exec", "-", "--ephemeral", "--skip-git-repo-check"]
        if input_image is not None:
            cmd.extend(["-i", str(input_image)])

        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)

        try:
            proc = subprocess.run(
                cmd,
                input=full_prompt.encode("utf-8"),
                capture_output=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            raise CodexImageError(f"codex exec timed out after {timeout}s") from e
        except FileNotFoundError as e:
            raise CodexImageError(f"codex binary not found: {codex_bin}") from e

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")[-300:]
            raise CodexImageError(f"codex rc={proc.returncode}: {stderr}")

        # 本次专属 images dir — 不会有任何其他来源的图
        img_dir = home / "generated_images"
        candidates: list[Path] = []
        if img_dir.exists():
            candidates = list(img_dir.rglob("*.png"))
        if not candidates:
            stdout_tail = proc.stdout.decode("utf-8", errors="replace")[-300:]
            raise CodexImageError(
                f"no PNG produced in isolated home {home}. stdout tail: {stdout_tail!r}"
            )
        # 隔离 home 里通常只会有 1 张；保险起见取最新 mtime
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


def _source_to_white_bg(source_image: Path, cache_path: Path | None = None) -> Image.Image:
    """rembg 去背景 → 白底合成。cache_path 提供时会缓存结果（首次慢 ~2s，后续命中即时）。"""
    if cache_path and cache_path.exists():
        with Image.open(cache_path) as im:
            return im.convert("RGB").copy()
    from rembg import remove
    with Image.open(source_image) as src:
        rgba = remove(src.convert("RGBA"))  # 抠图，返回 RGBA
    # 白底合成
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
    """特写图 = 抠图去背景 → 白底合成 → 局部 crop + 放大。**不走 Codex**（不改产品内容）。
    - front:  中央 70% 方形区
    - side:   中央偏右 60% 方形区
    - detail: 中央 35% 紧凑放大
    cutout_cache：可选 — 命中的白底 jpg 路径（让多张特写共享一次 rembg 抠图，省 ~2s × 2）
    输出 1024x1024 JPEG。
    """
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
        # 特写图改为 PIL 局部裁剪 + 放大，不走 Codex。这里只保留一个说明性文本给 preview 用。
        descriptions = {
            "front": "中央 70% 方形区裁剪放大（正面）",
            "side":  "中央偏右 60% 方形区裁剪放大（侧面）",
            "detail": "中央 35% 紧凑方形区裁剪放大（局部细节）",
        }
        return (
            f"[特写图] {descriptions.get(ratio_key, ratio_key)}\n"
            f"实现方式：PIL 从原图直接 crop + 放大（不调 Codex，不改图内容）。\n"
            f"输出尺寸：{size_hint} JPEG。"
        )

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
