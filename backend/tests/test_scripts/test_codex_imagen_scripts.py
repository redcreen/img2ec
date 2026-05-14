from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

from PIL import Image


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_script(name: str):
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tiny_jpeg(path: Path) -> None:
    Image.new("RGB", (12, 12), (220, 180, 80)).save(path, "JPEG")


def test_isolated_codex_runner_creates_distinct_session_home_per_generation(tmp_path):
    mod = _load_script("isolated_codex_image.py")
    real_home = tmp_path / "real-codex-home"
    real_home.mkdir()
    (real_home / "auth.json").write_text("{}", encoding="utf-8")

    homes: list[Path] = []
    commands: list[list[str]] = []

    def fake_run(cmd, *, env, timeout, capture_output, text, check, input):
        del timeout, capture_output, text, check, input
        commands.append(cmd)
        home = Path(env["CODEX_HOME"])
        homes.append(home)
        thread_id = f"thread-{len(homes)}"
        image_dir = home / "generated_images" / thread_id
        image_dir.mkdir(parents=True)
        Image.new("RGB", (64, 96), (230, 210, 160)).save(image_dir / "ig.png", "PNG")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"thread_id": thread_id}) + "\n",
            stderr="",
        )

    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    mod.generate_image(
        prompt="one",
        out=first,
        refs=[],
        timeout_sec=10,
        real_codex_home=real_home,
        run_fn=fake_run,
    )
    mod.generate_image(
        prompt="two",
        out=second,
        refs=[],
        timeout_sec=10,
        real_codex_home=real_home,
        run_fn=fake_run,
    )

    assert first.exists()
    assert second.exists()
    assert homes[0] != homes[1]
    assert not homes[0].exists()
    assert not homes[1].exists()
    for cmd in commands:
        assert "--ephemeral" in cmd
        assert "--enable" in cmd
        assert "image_generation" in cmd
        assert "--ignore-user-config" in cmd
        assert "--ignore-rules" in cmd


def test_duanwu_probe_passes_only_product_image_as_generation_ref(tmp_path, monkeypatch):
    mod = _load_script("duanwu_codex_imagen_probe.py")
    product = tmp_path / "8hao.jpg"
    compare = tmp_path / "8hao-chatgpt1-project-duanwupng.png"
    out = tmp_path / "duanwu-out.png"
    manifest = tmp_path / "duanwu-out.manifest.json"
    _tiny_jpeg(product)
    Image.new("RGB", (12, 18), (245, 238, 220)).save(compare, "PNG")

    call: dict[str, object] = {}

    def fake_generate_image(*, prompt, out, refs, timeout_sec, manifest=None):
        del manifest
        call["prompt"] = prompt
        call["out"] = Path(out)
        call["refs"] = list(refs)
        call["timeout_sec"] = timeout_sec
        Image.new("RGB", (64, 96), (230, 210, 160)).save(out, "PNG")
        return {"output": str(out), "thread_id": "fake-thread"}

    monkeypatch.setattr(mod._image_runner, "generate_image", fake_generate_image)

    rc = mod.main([
        "--product-image", str(product),
        "--out", str(out),
        "--compare-against", str(compare),
        "--manifest", str(manifest),
        "--timeout-sec", "11",
    ])

    assert rc == 0
    assert call["refs"] == [product.resolve()]
    assert compare.resolve() not in call["refs"]
    assert "chatgpt1" not in str(call["prompt"]).lower()
    assert "chatgpt" not in str(call["prompt"]).lower()
    assert out.exists()

    data = json.loads(manifest.read_text())
    assert data["generation_refs"] == [str(product.resolve())]
    assert data["compare_against"] == str(compare.resolve())


def test_legacy_codex_smoke_script_does_not_scan_global_generated_images():
    source = (SCRIPTS_DIR / "test_codex_image.py").read_text()

    assert "~/.codex" not in source
    assert "generated_images" not in source
    assert ".rglob(" not in source
    assert "generate_background_image" in source
