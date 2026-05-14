"""Smoke test Codex scene generation with the isolated codex-imagen backend.

This is a developer smoke script, not a production pipeline entrypoint. It
uses ``img2ec.infra.codex_image.generate_background_image()``, which delegates
to the installed codex-imagen wrapper. That wrapper owns per-call isolation and
returns the exact image for the current request.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image

from img2ec.core.composite import composite_cutout_on_background
from img2ec.core.cutout import cutout_with_rembg
from img2ec.infra.codex_image import generate_background_image

OUT = Path("/tmp/img2ec_codex_test")
OUT.mkdir(parents=True, exist_ok=True)


def generate_via_codex(
    prompt: str,
    target_path: Path,
    *,
    ratio_key: str = "1x1",
    timeout: int = 240,
) -> Path:
    """Ask Codex for one background via the isolated project backend."""
    return generate_background_image(
        prompt=prompt,
        ratio_key=ratio_key,
        output_path=target_path,
        timeout=timeout,
    )


def main() -> int:
    src = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / "img2ec" / "test.jpg"
    if not src.exists():
        print(f"FAIL: no test image at {src}")
        return 1

    print("[1/4] rembg cutout from real photo ...")
    cutout = OUT / "tiger_cutout.png"
    cutout_with_rembg(src, cutout)
    print(f"      {cutout} ({cutout.stat().st_size//1024}KB)")

    print("\n[2/4] Codex generates isolated 1:1 marble background ...")
    bg = OUT / "bg_codex_1x1.jpg"
    t0 = time.time()
    generate_via_codex(
        "white marble surface with subtle veining, warm soft window light from the upper-left, "
        "premium product photography studio look, shallow depth-of-field background blur",
        bg,
        ratio_key="1x1",
    )
    print(f"      {bg} ({bg.stat().st_size//1024}KB) in {time.time()-t0:.1f}s")

    print("\n[3/4] composite product cutout onto Codex background ...")
    out = OUT / "master_codex_1x1.jpg"
    composite_cutout_on_background(
        cutout_path=cutout,
        background_path=bg,
        output_path=out,
        ratio_key="1x1",
    )
    with Image.open(out) as img:
        print(f"      {out} ({img.size}, {out.stat().st_size//1024}KB)")

    print("\n=== compare ===")
    print(f"  open {out}")
    print("  compare against the previous Flux baseline manually if needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
