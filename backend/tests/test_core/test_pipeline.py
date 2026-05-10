"""Path C pipeline: Codex 直接 image-to-image，跳过 rembg + composite。"""
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
def test_pipeline_calls_master_gen_and_derive(mock_master, mock_derive, setup_dirs, tmp_path):
    """Path C 流程：直接走 generate_all_masters → derive，无 cutout 阶段。"""
    sku_dir, src = setup_dirs
    mock_master.return_value = {k: tmp_path / f"m-{k}.jpg" for k in ("1x1", "long", "3x4", "9x16", "16x9")}
    mock_derive.return_value = {"douyin": [tmp_path / "out.jpg"]}

    progress: list[tuple[str, int]] = []
    process_one_image(
        src_path=src,
        sku_dir=sku_dir,
        image_stem="front",
        scene_prompt="walnut tabletop",
        scene_neg="cluttered",
        ip_weight=60,
        seed=1,
        comfy_client=MagicMock(),
        workflows_dir=Path("workflows"),
        on_progress=lambda stage, pct: progress.append((stage, pct)),
    )

    mock_master.assert_called_once()
    mock_derive.assert_called_once()
    # Path C 没有 cutting 阶段（rembg 已被 Codex 多模态替代）
    stages = {s for s, _ in progress}
    assert "cutting" not in stages
    assert "generating" in stages
    assert "composing" in stages


@patch("img2ec.core.pipeline.derive_all_for_image")
@patch("img2ec.core.pipeline.generate_all_masters")
def test_pipeline_passes_source_image_to_master_gen(mock_master, mock_derive, setup_dirs, tmp_path):
    """master_gen 现在接收 source_image（而非 cutout_path）— Codex 直接吃源图。"""
    sku_dir, src = setup_dirs
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

    call_kwargs = mock_master.call_args.kwargs
    assert call_kwargs["source_image"] == src
    assert "cutout_path" not in call_kwargs
