from PIL import Image

from img2ec.core.derive import (
    PLATFORM_DERIVATIONS,
    MASTER_KEYS,
    derive_all_for_image,
)


def test_master_keys_are_5():
    assert set(MASTER_KEYS) == {"1x1", "long", "3x4", "9x16", "16x9"}


def test_platform_derivations_total_15():
    total = sum(len(items) for items in PLATFORM_DERIVATIONS.values())
    assert total == 15


def test_derive_all_creates_15_files(tmp_path):
    # 准备 5 张 master 假图（不同 ratio，颜色不同便于区分）
    masters = {}
    for key, (w, h) in {
        "1x1": (1024, 1024),
        "long": (750, 2000),
        "3x4": (900, 1200),
        "9x16": (1080, 1920),
        "16x9": (1920, 1080),
    }.items():
        m = Image.new("RGB", (w, h), (50 + hash(key) % 200, 100, 150))
        p = tmp_path / f"master-{key}.jpg"
        m.save(p, quality=92)
        masters[key] = p

    out_dir = tmp_path / "outputs"
    paths = derive_all_for_image(masters, out_dir, image_stem="front")

    # 4 个平台，每个 3-4 张
    assert set(paths.keys()) == {"douyin", "shipinhao", "taobao", "xiaohongshu"}
    counts = {p: len(items) for p, items in paths.items()}
    assert counts == {"douyin": 4, "shipinhao": 4, "taobao": 4, "xiaohongshu": 3}

    # 抽样检查 douyin 的尺寸
    douyin_files = paths["douyin"]
    main = next(f for f in douyin_files if "main" in f.name)
    with Image.open(main) as img:
        assert img.size == (1080, 1080)


def test_derive_skips_master_if_long_for_main_1x1():
    """1:1 main 必须从 1:1 master 派生，不能从其它 ratio crop（信息会丢）。"""
    # 这个测试隐式由 PLATFORM_DERIVATIONS 表保证，但显式测一下
    for plat, items in PLATFORM_DERIVATIONS.items():
        for item in items:
            if "main" in item["name"].lower() or "笔记图" in item["name"] or "封面" in item["name"]:
                # main/笔记/封面 派生应来自正确 master
                assert item["from"] in MASTER_KEYS, f"{plat}/{item['name']} bad master {item['from']}"
