"""一次性给 DEFAULT_SCENES 中所有还没 cover 的 seed 生成 cover 图。

用法：
    cd backend && .venv/bin/python scripts/generate_seed_covers.py

Codex 已有的 cover 文件会被跳过。每张 ~50s，并发=1（避免 Codex CLI 互相干扰）。
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from img2ec.seeds.default_scenes import DEFAULT_SCENES
from img2ec.infra.codex_image import generate_background_image, CodexImageError

COVERS_DIR = ROOT / "assets" / "scene_covers"
COVERS_DIR.mkdir(parents=True, exist_ok=True)

todo = [s for s in DEFAULT_SCENES if s.cover_filename and not (COVERS_DIR / s.cover_filename).exists()]
print(f"DEFAULT_SCENES total = {len(DEFAULT_SCENES)}")
print(f"already exist        = {sum(1 for s in DEFAULT_SCENES if s.cover_filename and (COVERS_DIR / s.cover_filename).exists())}")
print(f"to generate          = {len(todo)}")
print()

if not todo:
    print("nothing to do")
    sys.exit(0)

# 用 1:1 作为预览（cover 是缩略图，1024×1024 够用）
for i, seed in enumerate(todo, 1):
    out = COVERS_DIR / seed.cover_filename
    print(f"[{i}/{len(todo)}] {seed.festival} · {seed.name}  →  {out.name}")
    try:
        generate_background_image(
            prompt=seed.prompt,
            ratio_key="1x1",
            output_path=out,
            timeout=240,
        )
        size_kb = out.stat().st_size // 1024
        print(f"        ok ({size_kb}KB)")
    except CodexImageError as e:
        print(f"        FAIL: {e}")
    except Exception as e:
        print(f"        FAIL: {type(e).__name__}: {e}")

print()
print("done")
