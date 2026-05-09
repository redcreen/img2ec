"""E2E 测试用 mock ComfyUI（不依赖 gpu box）。"""
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image


@pytest.fixture
def mock_comfy(monkeypatch, tmp_path):
    """Mock ComfyClient：跳过真实 HTTP，直接生成一张占位 1:1 master。"""
    def fake_generate(*, output_path, **_):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1500, 1500), (200, 100, 50))
        img.save(output_path, quality=92)
        return Path(output_path)

    monkeypatch.setattr("img2ec.core.pipeline.generate_master_1x1", fake_generate)
    yield
