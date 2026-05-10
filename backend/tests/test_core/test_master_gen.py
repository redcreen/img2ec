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


def _make_source_photo(tmp_path: Path) -> Path:
    """A source product photo (商品 with cluttered background, simulates user upload)."""
    img = Image.new("RGB", (800, 800), (220, 200, 180))  # cluttered bg color
    p = tmp_path / "source.jpg"
    img.save(p, "JPEG", quality=92)
    return p


def test_generate_all_masters_via_codex_native_path(tmp_path, monkeypatch):
    """Path C: Codex 直接 image-to-image — 单次调用出含商品的 master，无 rembg/composite."""
    source = _make_source_photo(tmp_path)
    out_dir = tmp_path / "master"

    def fake_codex_master(*, source_image, scene_prompt, ratio_key, output_path, **kw):
        Image.new("RGB", (1024, 1024), (200, 50, 50)).save(output_path, "JPEG", quality=92)
        return output_path

    monkeypatch.setattr("img2ec.core.master_gen.generate_master_from_input", fake_codex_master)

    paths = generate_all_masters(
        client=None,
        workflows_dir=Path("/nonexistent"),
        source_image=source,
        prompt="walnut tabletop",
        negative_prompt="cluttered",
        ip_weight=60,
        seed=42,
        out_dir=out_dir,
        image_stem="front",
    )

    assert set(paths.keys()) == {"1x1", "long", "3x4", "9x16", "16x9"}
    for key, p in paths.items():
        assert p.exists(), f"master {key} not written via codex"


def test_generate_all_masters_via_comfyui_fallback_path(tmp_path, monkeypatch):
    """Path A fallback: ComfyUI Flux + rembg + PIL composite."""
    source = _make_source_photo(tmp_path)
    mock_client = _stub_comfy_client()
    workflows_dir = Path(__file__).parents[2] / "workflows"
    out_dir = tmp_path / "master"

    # Path A path needs rembg cutout + composite — mock both to keep test fast/offline
    def fake_cutout(src, dst):
        Image.new("RGBA", (200, 300), (200, 50, 50, 255)).save(dst, "PNG")

    def fake_composite(*, cutout_path, background_path, output_path, ratio_key):
        Image.new("RGB", (1024, 1024), (200, 50, 50)).save(output_path, "JPEG", quality=92)
        return output_path

    monkeypatch.setattr("img2ec.core.master_gen.cutout_with_rembg", fake_cutout)
    monkeypatch.setattr("img2ec.core.master_gen.composite_cutout_on_background", fake_composite)

    paths = generate_all_masters(
        client=mock_client,
        workflows_dir=workflows_dir,
        source_image=source,
        prompt="on marble",
        negative_prompt="cluttered",
        ip_weight=60,
        seed=42,
        out_dir=out_dir,
        image_stem="front",
        use_codex=False,
    )

    assert set(paths.keys()) == {"1x1", "long", "3x4", "9x16", "16x9"}
    for key, p in paths.items():
        assert p.exists()
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
