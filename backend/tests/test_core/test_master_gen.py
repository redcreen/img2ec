from pathlib import Path
from unittest.mock import MagicMock

from img2ec.core.master_gen import generate_master_1x1


def test_generate_master_calls_comfy_correctly(tmp_path):
    cutout = tmp_path / "front.png"
    cutout.write_bytes(b"fake png")
    out = tmp_path / "front-1x1.jpg"

    mock_client = MagicMock()
    mock_client.upload_image.return_value = "front.png"
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
    mock_client.upload_image.assert_called_once_with(cutout)
    mock_client.submit_prompt.assert_called_once()
    mock_client.wait_for_result.assert_called_once_with("pid-123")
