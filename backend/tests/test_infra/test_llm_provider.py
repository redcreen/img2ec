import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from img2ec.infra.llm_provider import CodexCLIProvider, LLMProviderError


def _make_completed_proc(stdout: str = "", stderr: str = "", rc: int = 0):
    cp = subprocess.CompletedProcess(args=["codex"], returncode=rc, stdout=stdout.encode(), stderr=stderr.encode())
    return cp


@patch("img2ec.infra.llm_provider.subprocess.run")
def test_generate_structured_writes_output(mock_run, tmp_path):
    """模拟 codex exec 写出 output.json。"""
    def fake_run(cmd, **kw):
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_text(json.dumps({"title": "测试", "tags": ["a", "b"]}))
        return _make_completed_proc()

    mock_run.side_effect = fake_run
    provider = CodexCLIProvider()
    result = provider.generate_structured(
        prompt="生成一个标题",
        json_schema={"type": "object", "properties": {"title": {"type": "string"}}},
    )
    assert result == {"title": "测试", "tags": ["a", "b"]}


@patch("img2ec.infra.llm_provider.subprocess.run")
def test_generate_structured_with_image(mock_run, tmp_path):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"fake")

    captured_cmd = []
    def fake_run(cmd, **kw):
        captured_cmd.extend(cmd)
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_text("{}")
        return _make_completed_proc()

    mock_run.side_effect = fake_run
    provider = CodexCLIProvider()
    provider.generate_structured(prompt="x", json_schema={}, image_path=img)
    assert "-i" in captured_cmd
    assert str(img) in captured_cmd


@patch("img2ec.infra.llm_provider.subprocess.run")
def test_nonzero_rc_raises(mock_run):
    mock_run.return_value = _make_completed_proc(stderr="boom", rc=1)
    provider = CodexCLIProvider()
    with pytest.raises(LLMProviderError, match="rc=1"):
        provider.generate_structured(prompt="x", json_schema={})


@patch("img2ec.infra.llm_provider.subprocess.run")
def test_invalid_json_raises(mock_run, tmp_path):
    def fake_run(cmd, **kw):
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_text("not valid json")
        return _make_completed_proc()

    mock_run.side_effect = fake_run
    provider = CodexCLIProvider()
    with pytest.raises(LLMProviderError, match="invalid JSON"):
        provider.generate_structured(prompt="x", json_schema={})


@patch("img2ec.infra.llm_provider.subprocess.run")
def test_timeout_raises(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["codex"], timeout=5)
    provider = CodexCLIProvider()
    with pytest.raises(LLMProviderError, match="timed out"):
        provider.generate_structured(prompt="x", json_schema={}, timeout=5)
