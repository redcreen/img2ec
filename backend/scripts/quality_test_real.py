"""Quality test with REAL product photo (instead of synthetic PIL cutout).

Runs full pipeline (bg_detect → rembg → 5 master via Flux + IPAdapter → 15 derive)
on a user-supplied product photo. Outputs to /tmp/img2ec_quality/ for visual comparison.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/quality_test_real.py [path/to/photo.jpg]

Default photo: ~/img2ec/test.jpg
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from img2ec.core.pipeline import process_one_image
from img2ec.infra.comfy_client import ComfyClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = BACKEND_DIR / "workflows"
COMFY_URL = "http://192.168.2.20:8188"

# 选用大理石场景 (Phase 1.5 验证过的 baseline)
SCENE_PROMPT = (
    "product on a white marble surface, warm soft window light from the left, "
    "45-degree camera angle, premium product photography, shallow depth of field, "
    "minimal composition, natural shadows"
)
SCENE_NEG = "cluttered, harsh light, oversaturated, low quality, watermark, text"
IP_WEIGHT = 60  # 0.6 in workflow
SEED = 42


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "img2ec" / "test.jpg"
    if not src.exists():
        print(f"FAIL: photo not found at {src}")
        return 1

    out_dir = Path("/tmp/img2ec_quality") / src.stem
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Copy original alongside outputs for reference
    shutil.copy2(src, out_dir / f"_input{src.suffix}")

    print(f"=== quality test: {src.name} ({src.stat().st_size//1024}KB) ===")
    print(f"    output dir: {out_dir}")

    client = ComfyClient(COMFY_URL, timeout=600)
    try:
        t0 = time.time()
        derived = process_one_image(
            src_path=src,
            sku_dir=out_dir,
            image_stem=src.stem,
            scene_prompt=SCENE_PROMPT,
            scene_neg=SCENE_NEG,
            ip_weight=IP_WEIGHT,
            seed=SEED,
            comfy_client=client,
            workflows_dir=WORKFLOWS_DIR,
            on_progress=lambda stage, pct: print(f"  [{stage}] {pct}%"),
        )
        elapsed = time.time() - t0
    finally:
        client.close()

    print(f"\n=== done in {elapsed:.1f}s ===")
    print(f"\nMaster outputs (5):")
    for f in sorted((out_dir / "master").glob("*.jpg")):
        from PIL import Image
        with Image.open(f) as img:
            print(f"  {f.name}: {img.size} ({f.stat().st_size//1024}KB)")
    print(f"\nDerived outputs (per-platform):")
    for plat, paths in derived.items():
        print(f"  {plat}: {len(paths)} files")
    print(f"\nView results in Finder:")
    print(f"  open {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
