from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from img2ec.core.pipeline import process_one_image


def test_e2e_pipeline_with_white_bg(tmp_path, fixtures_dir, mock_comfy):
    sku_d = tmp_path / "sku"
    sku_d.mkdir()

    derived = process_one_image(
        src_path=fixtures_dir / "white_bg.jpg",
        sku_dir=sku_d,
        image_stem="front",
        scene_prompt="on white marble, warm light",
        scene_neg="cluttered",
        ip_weight=60,
        seed=42,
        comfy_client=MagicMock(),
        workflow_path=Path("workflows/generate_master_1x1.json"),
    )

    assert set(derived.keys()) == {"douyin", "shipinhao", "taobao", "xiaohongshu"}
    for path in derived.values():
        assert path.exists()
        with Image.open(path) as img:
            assert img.size in [(1080, 1080), (800, 800)]


def test_e2e_pipeline_with_photo_bg_runs_cutout(tmp_path, fixtures_dir, mock_comfy):
    sku_d = tmp_path / "sku"
    sku_d.mkdir()

    derived = process_one_image(
        src_path=fixtures_dir / "photo_bg.jpg",
        sku_dir=sku_d,
        image_stem="side",
        scene_prompt="on marble",
        scene_neg="cluttered",
        ip_weight=60,
        seed=42,
        comfy_client=MagicMock(),
        workflow_path=Path("workflows/generate_master_1x1.json"),
    )

    # cutout/ 目录下应有抠图结果
    assert (sku_d / "cutout" / "side.png").exists()
    assert len(derived) == 4
