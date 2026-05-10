"""Real Codex CLI smoke for copy_gen on a real product image.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/quality_test_copy.py [path/to/image.jpg]

Default image: ~/img2ec/test.jpg
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from img2ec.core.copy_gen import generate_copy_for_sku
from img2ec.infra.llm_provider import CodexCLIProvider


def main() -> int:
    img = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "img2ec" / "test.jpg"
    if not img.exists():
        print(f"FAIL: {img} not found")
        return 1

    print(f"=== copy_gen smoke: {img.name} ===")
    t0 = time.time()
    try:
        result = generate_copy_for_sku(
            provider=CodexCLIProvider(),
            image_path=img,
            sku_name="蓝色刺绣布艺老虎摆件",
            scene_name="大理石台·暖光",
            scene_category="美妆/食品",
            timeout=300,
        )
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 2
    elapsed = time.time() - t0
    print(f"\n=== done in {elapsed:.1f}s ===\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Sanity checks
    print("\n=== sanity checks ===")
    assert "vlm" in result, "missing vlm"
    assert "douyin" in result, "missing douyin"
    assert "shipinhao" in result, "missing shipinhao"
    assert "xiaohongshu" in result, "missing xiaohongshu"
    print(f"  抖店 title: {len(result['douyin']['title'])} chars (limit 60)")
    print(f"  视频号 title: {len(result['shipinhao']['title'])} chars (limit 30)")
    print(f"  小红书 post_title: {len(result['xiaohongshu']['post_title'])} chars (limit 20)")
    print(f"  selling_points: 抖店={len(result['douyin']['selling_points'])} 视频号={len(result['shipinhao']['selling_points'])} 小红书={len(result['xiaohongshu']['selling_points'])}")
    print(f"  hashtags: {len(result['xiaohongshu']['hashtags'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
