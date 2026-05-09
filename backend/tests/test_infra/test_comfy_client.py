import json
from pathlib import Path
from unittest.mock import patch

import pytest

from img2ec.infra.comfy_client import ComfyClient, ComfyError


@pytest.fixture
def workflow_path(tmp_path):
    p = tmp_path / "wf.json"
    p.write_text(json.dumps({
        "1": {"class_type": "LoadImage", "inputs": {"image": "__CUTOUT__"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "__PROMPT__"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "__NEG__"}},
        "4": {"class_type": "IPAdapterApply", "inputs": {"weight": "__IP_WEIGHT__"}},
        "5": {"class_type": "KSampler", "inputs": {"seed": "__SEED__"}},
    }))
    return p


def test_substitute_placeholders(workflow_path):
    c = ComfyClient("http://gpu:8188")
    rendered = c.render_workflow(
        workflow_path,
        cutout="front.png",
        prompt="on marble",
        neg="cluttered",
        ip_weight=60,
        seed=42,
    )
    nodes = rendered
    assert nodes["1"]["inputs"]["image"] == "front.png"
    assert nodes["2"]["inputs"]["text"] == "on marble"
    assert nodes["3"]["inputs"]["text"] == "cluttered"
    assert nodes["4"]["inputs"]["weight"] == 60
    assert nodes["5"]["inputs"]["seed"] == 42


@patch("img2ec.infra.comfy_client.httpx.Client.post")
def test_submit_prompt_returns_id(mock_post):
    mock_post.return_value.json.return_value = {"prompt_id": "abc123"}
    mock_post.return_value.raise_for_status = lambda: None
    c = ComfyClient("http://gpu:8188")
    pid = c.submit_prompt({"1": {"class_type": "X", "inputs": {}}})
    assert pid == "abc123"


@patch("img2ec.infra.comfy_client.httpx.Client.post")
def test_submit_prompt_raises_on_http_error(mock_post):
    mock_post.side_effect = Exception("connection refused")
    c = ComfyClient("http://gpu:8188")
    with pytest.raises(ComfyError):
        c.submit_prompt({})
