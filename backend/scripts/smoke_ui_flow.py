"""End-to-end UI flow smoke test via API (no Redis/Celery worker needed).

Requires:
  - IMG2EC_CELERY_EAGER=true (Celery runs in-process)
  - IMG2EC_COMFY_URL pointing at a working ComfyUI (default 192.168.2.20:8188)
  - uvicorn running on http://localhost:8000

Steps:
  1. POST /api/projects → create test project (with default scene)
  2. GET /api/projects/<pid>/scenes → list scenes
  3. POST /api/projects/<pid>/skus → create SKU bound to default scene
  4. POST /api/projects/<pid>/skus/<sid>/images → upload a generated test image
  5. POST /api/projects/<pid>/skus/<sid>/process → trigger pipeline (synchronous in eager mode)
  6. GET /api/projects/<pid>/skus/<sid> → poll until done/error
  7. Verify outputs on disk + zip download

Usage:
  cd backend && source .venv/bin/activate
  IMG2EC_CELERY_EAGER=true uvicorn img2ec.main:app --port 8000 &
  IMG2EC_CELERY_EAGER=true python scripts/smoke_ui_flow.py
"""
from __future__ import annotations

import io
import sys
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

import os
API = os.environ.get("IMG2EC_API", "http://localhost:8001")
TIMEOUT = httpx.Timeout(connect=5, read=900, write=30, pool=10)  # Phase 2: 5 master = ~5 min


def make_test_image() -> bytes:
    """Generate a 'product' photo: solid color background + centered shape."""
    img = Image.new("RGB", (800, 800), (240, 230, 220))
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 200, 600, 600], fill=(80, 110, 200))
    draw.rectangle([350, 350, 450, 550], fill=(40, 60, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def main() -> int:
    print(f"=== UI flow smoke against {API} ===")
    project_name = f"smoke-{uuid.uuid4().hex[:6]}"

    with httpx.Client(base_url=API, timeout=TIMEOUT, trust_env=False) as cli:
        # 0. health
        r = cli.get("/api/health")
        if r.status_code != 200:
            print(f"FAIL: health: {r.status_code} {r.text}")
            return 1
        print("[0] health OK")

        # 1. create project
        r = cli.post("/api/projects", json={"name": project_name, "desc": "smoke", "copy_default_scenes": True})
        if r.status_code != 201:
            print(f"FAIL: create project: {r.status_code} {r.text}")
            return 1
        project = r.json()
        pid = project["id"]
        print(f"[1] project created: id={pid}, name={project_name}, scene_count={project['scene_count']}")

        # 2. list scenes
        r = cli.get(f"/api/projects/{pid}/scenes")
        scenes = r.json()
        if not scenes:
            print("FAIL: no default scene seeded")
            return 1
        scene = scenes[0]
        print(f"[2] scene: {scene['name']} ({scene['category']})")

        # 3. create SKU
        sku_name = "smoke-cup"
        r = cli.post(f"/api/projects/{pid}/skus", json={"name": sku_name, "scene_id": scene["id"]})
        if r.status_code != 201:
            print(f"FAIL: create SKU: {r.status_code} {r.text}")
            return 1
        sku = r.json()
        sid = sku["id"]
        print(f"[3] SKU created: id={sid}, status={sku['status']}")

        # 4. upload image
        img_bytes = make_test_image()
        files = {"file": ("front.jpg", img_bytes, "image/jpeg")}
        r = cli.post(f"/api/projects/{pid}/skus/{sid}/images", files=files)
        if r.status_code != 201:
            print(f"FAIL: upload: {r.status_code} {r.text}")
            return 1
        sku = r.json()
        if sku["status"] != "ready" or len(sku["images"]) != 1:
            print(f"FAIL: post-upload status wrong: {sku}")
            return 1
        print(f"[4] image uploaded, SKU status={sku['status']}, images={len(sku['images'])}")

        # 5. process
        print(f"[5] triggering process (eager mode — will block ~100s on first ComfyUI call) ...")
        t0 = time.time()
        r = cli.post(f"/api/projects/{pid}/skus/{sid}/process")
        if r.status_code != 202:
            print(f"FAIL: process trigger: {r.status_code} {r.text}")
            return 1
        elapsed = time.time() - t0
        print(f"      process returned in {elapsed:.1f}s, body={r.json()}")

        # 6. final state
        r = cli.get(f"/api/projects/{pid}/skus/{sid}")
        sku = r.json()
        print(f"[6] final SKU status={sku['status']}")
        for img in sku["images"]:
            print(f"      image {img['name']}: status={img['status']}, "
                  f"derived={list(img['derived_paths'].keys())}")
            if img.get("err_msg"):
                print(f"      ERR: {img['err_msg']}")

        if sku["status"] != "done":
            print(f"FAIL: expected SKU done, got {sku['status']}")
            return 2

        # 7. verify outputs on disk
        outputs_root = Path.home() / "img2ec" / "projects" / project_name / sku_name / "outputs"
        platforms = list(outputs_root.glob("*/"))
        print(f"[7] outputs/ has {len(platforms)} platform dirs: {[p.name for p in platforms]}")
        for p in platforms:
            jpgs = list(p.glob("*.jpg"))
            for jpg in jpgs:
                with Image.open(jpg) as im:
                    print(f"      {p.name}/{jpg.name}: {im.size} {im.mode} ({jpg.stat().st_size} bytes)")

        # 8. zip download
        r = cli.get(f"/api/skus/{sid}/download")
        if r.status_code != 200 or len(r.content) < 1000:
            print(f"FAIL: zip download: {r.status_code} size={len(r.content)}")
            return 3
        zip_path = Path("/tmp") / f"{sku_name}.zip"
        zip_path.write_bytes(r.content)
        print(f"[8] zip downloaded: {zip_path} ({len(r.content)} bytes)")

    print("=== ALL OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
