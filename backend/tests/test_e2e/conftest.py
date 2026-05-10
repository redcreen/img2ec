"""E2E 测试用 mock ComfyUI（不依赖 gpu box）。"""
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def mock_comfy(monkeypatch, tmp_path):
    """Mock generate_all_masters：返回 5 张占位图。"""
    def fake_generate_all(*, out_dir, image_stem, **_):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        sizes = {"1x1": (1024, 1024), "long": (750, 2000), "3x4": (900, 1200), "9x16": (1080, 1920), "16x9": (1920, 1080)}
        out: dict = {}
        for key, (w, h) in sizes.items():
            p = out_dir / f"{image_stem}-{key}.jpg"
            img = Image.new("RGB", (w, h), (200, 100, 50))
            img.save(p, quality=92)
            out[key] = p
        return out

    monkeypatch.setattr("img2ec.core.pipeline.generate_all_masters", fake_generate_all)
    yield
