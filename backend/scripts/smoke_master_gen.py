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
    """Create a fake 'product' cutout (RGBA, transparent bg, centered colored shape)."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.ellipse([128, 128, 384, 384], fill=(50, 100, 200, 255))
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
            prompt="on white marble surface, warm soft window light, 45-degree angle, premium product photography",
            negative_prompt="cluttered, harsh light, oversaturated, low quality, watermark, text",
            ip_weight=60,
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
