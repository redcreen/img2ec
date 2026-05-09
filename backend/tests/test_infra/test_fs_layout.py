from pathlib import Path
import pytest

from img2ec.infra.fs_layout import slug, project_dir, sku_dir, source_dir, master_dir, outputs_dir, platform_dir


def test_slug_keeps_chinese():
    assert slug("蓝色保温杯 500ml") == "蓝色保温杯-500ml"


def test_slug_strips_special_chars():
    assert slug("a/b\\c?d:e*f") == "a-b-c-d-e-f"


def test_project_dir(tmp_path):
    root = tmp_path
    p = project_dir(root, "双11促销")
    assert p == root / "双11促销"


def test_sku_dir(tmp_path):
    p = sku_dir(tmp_path, "default", "蓝色保温杯")
    assert p == tmp_path / "default" / "蓝色保温杯"


def test_subdirs(tmp_path):
    skud = sku_dir(tmp_path, "default", "blue-cup")
    assert source_dir(skud) == skud / "source"
    assert master_dir(skud) == skud / "master"
    assert outputs_dir(skud) == skud / "outputs"
    assert platform_dir(skud, "douyin") == skud / "outputs" / "douyin"


def test_invalid_platform_rejected(tmp_path):
    skud = sku_dir(tmp_path, "p", "s")
    with pytest.raises(ValueError, match="invalid platform"):
        platform_dir(skud, "facebook")
