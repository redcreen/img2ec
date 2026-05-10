"""End-to-end smoke test for master_gen against real ComfyUI on gpu box.

Runs the core pipeline (without Celery/Redis) to validate ComfyUI integration.
Uses LAN IP `192.168.2.20:8188`. No 商品 cutout integration yet — Flux baseline workflow.

Usage:
    cd backend && source .venv/bin/activate && python scripts/smoke_master_gen.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image

from img2ec.core.master_gen import generate_master_1x1
from img2ec.infra.comfy_client import ComfyClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKFLOW = BACKEND_DIR / "workflows" / "generate_master_1x1.json"
COMFY_URL = "http://192.168.2.20:8188"
SEED = 42

OUT_DIR = Path("/tmp/img2ec_smoke")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_test_cutout() -> Path:
    """Create a fake 'product' cutout — large商品 (bottle-like shape) filling most of frame.

    IPAdapter extracts visual features from the whole image; sparse subjects on transparent
    bg produce weak embeddings.
    """
    from PIL import ImageDraw

    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # bottle body
    draw.rounded_rectangle([180, 100, 332, 470], radius=30, fill=(50, 100, 200, 255))
    # bottle neck
    draw.rectangle([230, 60, 282, 110], fill=(50, 100, 200, 255))
    # cap
    draw.rounded_rectangle([220, 30, 292, 75], radius=8, fill=(180, 180, 180, 255))
    # label
    draw.rectangle([195, 200, 317, 340], fill=(240, 240, 230, 255))
    draw.rectangle([210, 250, 302, 280], fill=(140, 30, 30, 255))
    path = OUT_DIR / "test_cutout.png"
    img.save(path)
    return path


def main() -> int:
    print(f"=== smoke test: master_gen against {COMFY_URL} ===")

    cutout = make_test_cutout()
    print(f"[1/4] generated test cutout: {cutout} ({cutout.stat().st_size} bytes)")

    output_path = OUT_DIR / "smoke_master_1x1.png"

    print(f"[2/4] connecting to ComfyUI at {COMFY_URL} ...")
    client = ComfyClient(COMFY_URL, timeout=180)
    try:
        # health check
        try:
            import httpx

            resp = httpx.get(f"{COMFY_URL}/system_stats", timeout=10, trust_env=False)
            resp.raise_for_status()
            print(f"      ComfyUI alive: {resp.json().get('system', {}).get('os', '?')}")
        except Exception as e:
            print(f"      ERROR: cannot reach ComfyUI: {e}")
            return 2

        print(f"[3/4] submitting workflow + waiting for output ...")
        t0 = time.time()
        result_path = generate_master_1x1(
            client=client,
            workflow_path=WORKFLOW,
            cutout_path=cutout,
            prompt="bottle on white marble surface, warm soft window light, 45-degree angle, premium product photography, sharp focus on product",
            negative_prompt="cluttered, harsh light, oversaturated, low quality, watermark, text",
            ip_weight=30,  # try lower weight; prompt needs more breathing room
            seed=SEED,
            output_path=output_path,
        )
        elapsed = time.time() - t0
        print(f"      done in {elapsed:.1f}s")

        if not result_path.exists():
            print(f"[4/4] FAIL: output {result_path} not created")
            return 3
        size = result_path.stat().st_size
        if size < 10_000:
            print(f"[4/4] FAIL: output too small ({size} bytes)")
            return 4

        with Image.open(result_path) as img:
            print(f"[4/4] OK: output {result_path} ({size} bytes, {img.size}, mode={img.mode})")
        return 0

    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
