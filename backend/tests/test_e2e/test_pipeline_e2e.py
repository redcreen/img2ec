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
        workflows_dir=Path("workflows"),
    )

    # 4 平台都有派生
    assert set(derived.keys()) == {"douyin", "shipinhao", "taobao", "xiaohongshu"}
    # 总共 15 张派生
    total = sum(len(paths) for paths in derived.values())
    assert total == 15

    # 5 张 master 都生成了
    master_dir = sku_d / "master"
    masters = list(master_dir.glob("front-*.jpg"))
    assert len(masters) == 5


def test_e2e_pipeline_path_c_no_cutout_dir(tmp_path, fixtures_dir, mock_comfy):
    """Path C 不再做 rembg 抠图，cutout/ 目录不应被创建。"""
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
        workflows_dir=Path("workflows"),
    )

    # Path C: 跳过 rembg，cutout 目录不应该存在/为空
    cutout_d = sku_d / "cutout"
    assert not cutout_d.exists() or not list(cutout_d.glob("*"))
    # 5 master + 15 派生 仍然出
    total = sum(len(paths) for paths in derived.values())
    assert total == 15
