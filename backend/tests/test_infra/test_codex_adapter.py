"""Adapter layer tests — 不真跑 codex CLI，全部 mock。"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from img2ec.infra import codex_adapter as ca


def test_is_refusal_matches_known_hints():
    assert ca.is_refusal("the agent refused to invoke image_generation tool")
    assert ca.is_refusal("Expected codex to write but the directory does not exist")
    assert ca.is_refusal("No PNG produced in isolated home")
    assert not ca.is_refusal("timed out after 600s")
    assert not ca.is_refusal("auth.json not found")


def test_generate_image_success(monkeypatch, tmp_path):
    """成功路径：gen.generate 返回 → 我们也返回。"""
    out = tmp_path / "out.png"

    fake_gen = MagicMock()
    fake_gen.GenError = type("GenError", (Exception,), {})
    def fake_generate(prompt, out_path, refs=None, timeout_sec=300):
        Path(out_path).write_bytes(b"x")
    fake_gen.generate.side_effect = fake_generate
    monkeypatch.setattr(ca, "_load_gen", lambda: fake_gen)

    got = ca.generate_image("hello", out, refs=[tmp_path / "ref.jpg"], timeout_sec=60)
    assert got == out
    fake_gen.generate.assert_called_once()


def test_generate_image_refusal_wraps_with_flag(monkeypatch, tmp_path):
    fake_gen = MagicMock()
    fake_gen.GenError = type("GenError", (Exception,), {})
    fake_gen.generate.side_effect = fake_gen.GenError("agent refused to invoke image_generation")
    monkeypatch.setattr(ca, "_load_gen", lambda: fake_gen)

    with pytest.raises(ca.AdapterError) as exc:
        ca.generate_image("x", tmp_path / "out.png")
    assert exc.value.refusal is True


def test_generate_image_non_refusal_wraps_without_flag(monkeypatch, tmp_path):
    fake_gen = MagicMock()
    fake_gen.GenError = type("GenError", (Exception,), {})
    fake_gen.generate.side_effect = fake_gen.GenError("codex exec timed out after 600s")
    monkeypatch.setattr(ca, "_load_gen", lambda: fake_gen)

    with pytest.raises(ca.AdapterError) as exc:
        ca.generate_image("x", tmp_path / "out.png")
    assert exc.value.refusal is False
