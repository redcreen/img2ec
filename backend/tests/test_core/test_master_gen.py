from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from img2ec.core.master_gen import _flatten_rgba_to_white_rgb, generate_master_1x1


def test_generate_master_calls_comfy_correctly(tmp_path):
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
    src = tmp_path / "transparent.png"
    img = Image.new("RGBA", (32, 32), (255, 0, 0, 128))
    img.save(src)

    out = _flatten_rgba_to_white_rgb(src)
    assert out.exists()
    assert out.suffix == ".jpg"
    with Image.open(out) as result:
        assert result.mode == "RGB"


def test_flatten_passthrough_for_rgb(tmp_path):
    src = tmp_path / "rgb.jpg"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(src)
    out = _flatten_rgba_to_white_rgb(src)
    assert out == src
