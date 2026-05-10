"""Real smoke for detail-page composition (LLM copy_gen + Pillow detail render).

Steps:
  1. Run copy_gen on a real image via Codex CLI (~1 min)
  2. Use the input image as both 1x1 and long master (smoke shortcut)
  3. Render the default 5-module detail page using douyin copy
  4. Print path + size; user opens visually

Usage:
  cd backend && source .venv/bin/activate && python scripts/quality_test_detail.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

from img2ec.core.copy_gen import generate_copy_for_sku
from img2ec.core.detail_page import render_detail_page
from img2ec.core.detail_template import DEFAULT_TEMPLATE
from img2ec.infra.llm_provider import CodexCLIProvider


def main() -> int:
    img = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "img2ec" / "test.jpg"
    if not img.exists():
        print(f"FAIL: {img} not found")
        return 1

    out_dir = Path("/tmp/img2ec_quality_detail")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] copy_gen via Codex CLI on {img.name} ...")
    copy = generate_copy_for_sku(
        provider=CodexCLIProvider(),
        image_path=img,
        sku_name="蓝色刺绣布艺老虎摆件",
        scene_name="大理石台·暖光",
        scene_category="美妆/食品",
        timeout=300,
    )
    douyin = copy["douyin"]
    print(f"      抖店标题: {douyin['title']}")
    print(f"      副标题: {douyin['subtitle']}")
    print(f"      卖点 ({len(douyin['selling_points'])}): {douyin['selling_points'][0]} ...")
    if douyin.get("video_script"):
        print(f"      视频脚本 (head 60 字): {douyin['video_script'][:60]}...")

    print(f"\n[2/3] preparing master images (using input as 1x1 + long for smoke) ...")
    p1 = out_dir / "master-1x1.jpg"
    Image.open(img).convert("RGB").save(p1, quality=92)
    plong = out_dir / "master-long.jpg"
    with Image.open(img) as src:
        rgb = src.convert("RGB")
        ratio = 750 / rgb.size[0]
        new_h = int(rgb.size[1] * ratio)
        rgb.resize((750, new_h), Image.LANCZOS).save(plong, quality=92)

    print(f"\n[3/3] rendering detail page via DEFAULT_TEMPLATE ...")
    out = out_dir / "detail.jpg"
    render_detail_page(
        template=DEFAULT_TEMPLATE,
        copy={
            "title": douyin["title"],
            "subtitle": douyin["subtitle"],
            "selling_points": douyin["selling_points"],
        },
        images={"1x1": p1, "long": plong},
        output_path=out,
    )

    with Image.open(out) as final:
        size = final.size
    print(f"\n=== OK ===")
    print(f"  detail page: {out}")
    print(f"  size: {size[0]}×{size[1]}, {out.stat().st_size//1024}KB")
    print(f"  view: open {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
