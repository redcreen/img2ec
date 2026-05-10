from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from img2ec.core.master_gen import MASTER_WORKFLOW_FILES, generate_all_masters, generate_master_1x1


def test_workflow_files_map_5_masters():
    assert set(MASTER_WORKFLOW_FILES.keys()) == {"1x1", "long", "3x4", "9x16", "16x9"}
    for name in MASTER_WORKFLOW_FILES.values():
        assert name.endswith(".json")


def _make_rgba_cutout(tmp_path: Path) -> Path:
    """A minimal RGBA cutout (red rectangle on transparent bg) for compositing tests."""
    img = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    for y in range(300):
        for x in range(200):
            if 50 <= x < 150 and 50 <= y < 250:
                img.putpixel((x, y), (200, 50, 50, 255))
    p = tmp_path / "cutout.png"
    img.save(p)
    return p


def _stub_comfy_client(bg_color: tuple[int, int, int] = (240, 230, 210)) -> MagicMock:
    """Mock ComfyClient that 'generates' a solid-color background image to disk."""
    mock = MagicMock()
    mock.render_workflow.return_value = {"k": {"class_type": "KSampler"}}
    mock.submit_prompt.side_effect = lambda w: f"pid-{id(w)}"
    mock.wait_for_result.return_value = {
        "outputs": {"12": {"images": [{"filename": "bg.png", "subfolder": "", "type": "output"}]}}
    }

    def fake_download(filename, subfolder, type_, dst_path):
        Image.new("RGB", (1024, 1024), bg_color).save(dst_path, "JPEG", quality=92)

    mock.download_output.side_effect = fake_download
    return mock


def test_generate_all_masters_produces_5_masters_with_cutout_composited(tmp_path):
    cutout = _make_rgba_cutout(tmp_path)
    mock_client = _stub_comfy_client()
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
    for key, p in paths.items():
        assert p.exists(), f"master {key} not written"
        with Image.open(p) as img:
            assert img.mode == "RGB"
            # cutout should appear; sample center pixels and look for red
            w, h = img.size
            mid_x, mid_y = w // 2, h // 2
            r, g, b = img.getpixel((mid_x, mid_y))
            assert r > g and r > b, f"{key} center pixel not red-dominant: {(r,g,b)}"
    # 5 ComfyUI calls (one per ratio)
    assert mock_client.submit_prompt.call_count == 5


def test_generate_master_1x1_backward_compat(tmp_path):
    cutout = _make_rgba_cutout(tmp_path)
    out = tmp_path / "front-1x1.jpg"
    mock_client = _stub_comfy_client((200, 200, 250))
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
    with Image.open(out) as img:
        assert img.mode == "RGB"
