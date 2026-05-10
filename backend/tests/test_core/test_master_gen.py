from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from img2ec.core.master_gen import (
    MASTER_WORKFLOW_FILES,
    _flatten_rgba_to_white_rgb,
    generate_all_masters,
    generate_master_1x1,
)


def test_workflow_files_map_5_masters():
    """Verify MASTER_WORKFLOW_FILES has 5 keys mapping to JSON filenames."""
    assert set(MASTER_WORKFLOW_FILES.keys()) == {"1x1", "long", "3x4", "9x16", "16x9"}
    for name in MASTER_WORKFLOW_FILES.values():
        assert name.endswith(".json")


def test_generate_all_masters_calls_comfy_5_times(tmp_path):
    """Test generate_all_masters submits 5 workflows, returns 5 paths."""
    # Create a proper PNG file (not fake binary)
    cutout = tmp_path / "front.png"
    img = Image.new("RGB", (64, 64), (100, 100, 100))
    img.save(cutout)

    mock_client = MagicMock()
    mock_client.upload_image.return_value = "front.png"
    mock_client.render_workflow.return_value = {"5": {"class_type": "KSampler"}}
    mock_client.submit_prompt.side_effect = lambda w: f"pid-{id(w)}"
    mock_client.wait_for_result.return_value = {
        "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}
    }

    download_calls = []

    def fake_download(filename, subfolder, type_, dst_path):
        Path(dst_path).write_bytes(b"fake jpg")
        download_calls.append(dst_path)

    mock_client.download_output.side_effect = fake_download

    workflows_dir = Path(__file__).parents[2] / "workflows"
    out_dir = tmp_path / "master"

    paths = generate_all_masters(
        client=mock_client,
        workflows_dir=workflows_dir,
        cutout_path=cutout,
        prompt="on marble",
        negative_prompt="cluttered",
        ip_weight=60,
        seed=42,
        out_dir=out_dir,
        image_stem="front",
    )

    assert set(paths.keys()) == {"1x1", "long", "3x4", "9x16", "16x9"}
    for k, p in paths.items():
        assert p.exists(), f"master {k} not written"
    assert mock_client.submit_prompt.call_count == 5


def test_backward_compat_generate_master_1x1_still_works(tmp_path):
    """Ensure Phase 1 generate_master_1x1 API still works (backward compat)."""
    # Create a proper PNG file
    cutout = tmp_path / "front.png"
    img = Image.new("RGB", (64, 64), (100, 100, 100))
    img.save(cutout)
    out = tmp_path / "front-1x1.jpg"

    mock_client = MagicMock()
    mock_client.upload_image.return_value = "front.png"
    mock_client.render_workflow.return_value = {}
    mock_client.submit_prompt.return_value = "pid"
    mock_client.wait_for_result.return_value = {
        "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}
    }

    def fake_download(filename, subfolder, type_, dst_path):
        Path(dst_path).write_bytes(b"x")

    mock_client.download_output.side_effect = fake_download

    workflow = Path(__file__).parents[2] / "workflows" / "generate_master_1x1.json"
    result = generate_master_1x1(
        client=mock_client,
        workflow_path=workflow,
        cutout_path=cutout,
        prompt="p",
        negative_prompt="n",
        ip_weight=60,
        seed=1,
        output_path=out,
    )
    assert result == out
    assert out.exists()


def test_generate_master_calls_comfy_correctly(tmp_path):
    """Test generate_master_1x1 with RGBA PNG flatten."""
    # Real RGBA PNG so the RGBA→white flattening works
    cutout = tmp_path / "front.png"
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    img.save(cutout)
    out = tmp_path / "front-1x1.jpg"

    mock_client = MagicMock()
    mock_client.upload_image.return_value = "front.jpg"
    mock_client.render_workflow.return_value = {"5": {"class_type": "KSampler"}}
    mock_client.submit_prompt.return_value = "pid-123"
    mock_client.wait_for_result.return_value = {
        "outputs": {
            "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
        }
    }

    def fake_download(filename, subfolder, type_, dst_path):
        Path(dst_path).write_bytes(b"fake jpg")

    mock_client.download_output.side_effect = fake_download

    workflow_path = Path(__file__).parents[2] / "workflows" / "generate_master_1x1.json"
    generate_master_1x1(
        client=mock_client,
        workflow_path=workflow_path,
        cutout_path=cutout,
        prompt="on marble",
        negative_prompt="cluttered",
        ip_weight=60,
        seed=42,
        output_path=out,
    )

    assert out.exists()
    # upload_image is now called with the flattened temp path (not the original RGBA cutout)
    assert mock_client.upload_image.call_count == 1
    uploaded = mock_client.upload_image.call_args.args[0]
    assert uploaded.suffix == ".jpg"
    mock_client.submit_prompt.assert_called_once()
    mock_client.wait_for_result.assert_called_once_with("pid-123")


def test_flatten_rgba_returns_jpg(tmp_path):
    """Test _flatten_rgba_to_white_rgb converts RGBA to RGB JPEG."""
    src = tmp_path / "transparent.png"
    img = Image.new("RGBA", (32, 32), (255, 0, 0, 128))
    img.save(src)

    out = _flatten_rgba_to_white_rgb(src)
    assert out.exists()
    assert out.suffix == ".jpg"
    with Image.open(out) as result:
        assert result.mode == "RGB"


def test_flatten_passthrough_for_rgb(tmp_path):
    """Test _flatten_rgba_to_white_rgb passes through RGB unchanged."""
    src = tmp_path / "rgb.jpg"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(src)
    out = _flatten_rgba_to_white_rgb(src)
    assert out == src
