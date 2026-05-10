from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from img2ec.core.pipeline import process_one_image


@pytest.fixture
def setup_dirs(tmp_path):
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src = src_dir / "front.jpg"
    src.write_bytes(b"fake jpg")
    return tmp_path, src


@patch("img2ec.core.pipeline.derive_all_for_image")
@patch("img2ec.core.pipeline.generate_all_masters")
@patch("img2ec.core.pipeline.cutout_with_rembg")
@patch("img2ec.core.pipeline.is_white_background")
def test_pipeline_white_bg_skips_cutout(
    mock_bg, mock_cut, mock_master, mock_derive, setup_dirs, tmp_path
):
    sku_dir, src = setup_dirs
    mock_bg.return_value = True
    mock_master.return_value = {k: tmp_path / f"m-{k}.jpg" for k in ("1x1", "long", "3x4", "9x16", "16x9")}
    mock_derive.return_value = {"douyin": [tmp_path / "out.jpg"]}

    progress: list[tuple[str, int]] = []
    process_one_image(
        src_path=src,
        sku_dir=sku_dir,
        image_stem="front",
        scene_prompt="p",
        scene_neg="n",
        ip_weight=60,
        seed=1,
        comfy_client=MagicMock(),
        workflows_dir=Path("workflows"),
        on_progress=lambda stage, pct: progress.append((stage, pct)),
    )

    mock_cut.assert_not_called()
    mock_master.assert_called_once()
    mock_derive.assert_called_once()
    stages = [s for s, _ in progress]
    assert "cutting" not in stages
    assert "generating" in stages
    assert "composing" in stages


@patch("img2ec.core.pipeline.derive_all_for_image")
@patch("img2ec.core.pipeline.generate_all_masters")
@patch("img2ec.core.pipeline.cutout_with_rembg")
@patch("img2ec.core.pipeline.is_white_background")
def test_pipeline_photo_bg_runs_cutout(
    mock_bg, mock_cut, mock_master, mock_derive, setup_dirs, tmp_path
):
    sku_dir, src = setup_dirs
    mock_bg.return_value = False
    mock_master.return_value = {k: tmp_path / f"m-{k}.jpg" for k in ("1x1", "long", "3x4", "9x16", "16x9")}
    mock_derive.return_value = {"douyin": [tmp_path / "out.jpg"]}

    process_one_image(
        src_path=src,
        sku_dir=sku_dir,
        image_stem="front",
        scene_prompt="p",
        scene_neg="n",
        ip_weight=60,
        seed=1,
        comfy_client=MagicMock(),
        workflows_dir=Path("workflows"),
    )

    mock_cut.assert_called_once()
    mock_master.assert_called_once()
