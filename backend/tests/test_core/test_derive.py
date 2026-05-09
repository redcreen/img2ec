from PIL import Image

from img2ec.core.derive import PLATFORMS_1X1_SIZES, derive_main_1x1_for_platforms


def test_platforms_have_expected_sizes():
    assert PLATFORMS_1X1_SIZES == {
        "douyin": (1080, 1080),
        "shipinhao": (800, 800),
        "taobao": (800, 800),
        "xiaohongshu": (1080, 1080),
    }


def test_derive_creates_per_platform_files(tmp_path):
    # 准备一张 1:1 master
    master = Image.new("RGB", (1500, 1500), (200, 100, 50))
    master_path = tmp_path / "master-1x1.jpg"
    master.save(master_path, quality=92)

    out_dir = tmp_path / "outputs"
    paths = derive_main_1x1_for_platforms(master_path, out_dir, image_stem="front")

    assert set(paths.keys()) == {"douyin", "shipinhao", "taobao", "xiaohongshu"}
    for platform, p in paths.items():
        assert p.exists()
        with Image.open(p) as img:
            assert img.size == PLATFORMS_1X1_SIZES[platform]


def test_derive_handles_non_square_master_by_center_crop(tmp_path):
    # 非 1:1 输入：测试中央裁切
    master = Image.new("RGB", (2000, 1500), (50, 50, 50))
    master_path = tmp_path / "master.jpg"
    master.save(master_path, quality=92)

    out_dir = tmp_path / "outputs"
    paths = derive_main_1x1_for_platforms(master_path, out_dir, image_stem="x")
    with Image.open(paths["douyin"]) as img:
        assert img.size == (1080, 1080)
