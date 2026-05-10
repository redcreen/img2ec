"""Sanity check: each workflow file is valid JSON with expected placeholders."""
import json
from pathlib import Path

import pytest

WORKFLOW_DIR = Path(__file__).parents[2] / "workflows"
EXPECTED_FILES = [
    "generate_master_1x1.json",
    "generate_master_long.json",
    "generate_master_3x4.json",
    "generate_master_9x16.json",
    "generate_master_16x9.json",
]


@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_workflow_is_valid_json(name):
    path = WORKFLOW_DIR / name
    assert path.exists(), f"missing {path}"
    data = json.loads(path.read_text())
    assert isinstance(data, dict), f"workflow {name} should be a dict"


@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_workflow_has_required_placeholders(name):
    raw = (WORKFLOW_DIR / name).read_text()
    for token in ("__PROMPT__", "__NEG__", "__SEED__", "__CUTOUT__", "__IP_WEIGHT__"):
        assert token in raw, f"workflow {name} missing {token}"


@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_workflow_has_ipadapter_nodes(name):
    """Every workflow uses IPAdapter Flux for 商品 injection."""
    data = json.loads((WORKFLOW_DIR / name).read_text())
    class_types = {node.get("class_type") for nid, node in data.items() if not nid.startswith("_")}
    assert "IPAdapterFluxLoader" in class_types
    assert "ApplyIPAdapterFlux" in class_types
    assert "LoadImage" in class_types


def test_5_workflows_have_distinct_filename_prefixes():
    """SaveImage filename_prefix should differ so outputs don't collide."""
    prefixes = []
    for name in EXPECTED_FILES:
        data = json.loads((WORKFLOW_DIR / name).read_text())
        save_node = next(n for nid, n in data.items() if not nid.startswith("_") and n.get("class_type") == "SaveImage")
        prefixes.append(save_node["inputs"]["filename_prefix"])
    assert len(set(prefixes)) == 5, f"duplicate prefixes: {prefixes}"
