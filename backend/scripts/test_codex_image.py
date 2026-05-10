"""Test using Codex CLI image generation as background, composite商品 on top.

Compares against current Flux pipeline (which produces washed-out marble).
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image

from img2ec.core.composite import composite_cutout_on_background
from img2ec.core.cutout import cutout_with_rembg

OUT = Path("/tmp/img2ec_codex_test")
OUT.mkdir(parents=True, exist_ok=True)
CODEX_IMG_DIR = Path.home() / ".codex" / "generated_images"


def generate_via_codex(prompt: str, target_path: Path, *, ratio: str = "1024x1024", timeout: int = 180) -> Path:
    """Ask Codex CLI to generate an image with given prompt + size hint.

    Reads the most-recently-modified PNG under ~/.codex/generated_images/ after exec.
    """
    before_ts = time.time()
    full_prompt = (
        f"Generate a single photographic image at {ratio} resolution. "
        f"Subject: {prompt} "
        f"Constraints: empty scene with NO product or person — just the background; "
        f"high resolution, sharp detail, no text, no watermark."
    )
    proc = subprocess.run(
        ["codex", "exec", "-", "--ephemeral", "--skip-git-repo-check"],
        input=full_prompt.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"codex rc={proc.returncode}: {proc.stderr.decode()[-300:]}")

    candidates = [p for p in CODEX_IMG_DIR.rglob("*.png") if p.stat().st_mtime >= before_ts - 1]
    if not candidates:
        raise RuntimeError(
            f"no new image produced. stdout tail: {proc.stdout.decode()[-300:]}"
        )
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(newest, target_path)
    return target_path


def main() -> int:
    src = Path.home() / "img2ec" / "test.jpg"
    if not src.exists():
        print(f"FAIL: no test image at {src}")
        return 1

    print("[1/4] rembg cutout from real photo …")
    cutout = OUT / "tiger_cutout.png"
    cutout_with_rembg(src, cutout)
    print(f"      {cutout} ({cutout.stat().st_size//1024}KB)")

    print("\n[2/4] Codex generates 1:1 marble background (~30-60s) …")
    bg = OUT / "bg_codex_1x1.png"
    t0 = time.time()
    generate_via_codex(
        "white marble surface with subtle veining, warm soft window light from the upper-left, "
        "premium product photography studio look, shallow depth-of-field background blur",
        bg,
        ratio="1024x1024",
    )
    print(f"      {bg} ({bg.stat().st_size//1024}KB) in {time.time()-t0:.1f}s")

    print("\n[3/4] composite tiger商品 onto Codex background …")
    out = OUT / "master_codex_1x1.jpg"
    composite_cutout_on_background(
        cutout_path=cutout, background_path=bg, output_path=out, ratio_key="1x1",
    )
    with Image.open(out) as img:
        print(f"      {out} ({img.size}, {out.stat().st_size//1024}KB)")

    print("\n=== compare ===")
    print(f"  open {out}")
    print(f"  open ~/img2ec/projects/端午节2/老虎/master/test-1x1.jpg   (Flux baseline)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
