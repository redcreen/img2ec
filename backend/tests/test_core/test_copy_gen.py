from pathlib import Path
from unittest.mock import MagicMock

from img2ec.core.copy_gen import COPY_OUTPUT_SCHEMA, generate_copy_for_sku


def test_schema_has_3_platforms():
    props = COPY_OUTPUT_SCHEMA["properties"]
    assert "douyin" in props
    assert "shipinhao" in props
    assert "xiaohongshu" in props
    assert "taobao" not in props  # 跳过


def test_schema_xhs_has_hashtags_not_keywords():
    xhs = COPY_OUTPUT_SCHEMA["$defs"]["platform_xhs"]
    assert "hashtags" in xhs["properties"]
    assert "keywords" not in xhs["properties"]


def test_generate_copy_calls_provider_with_image(tmp_path):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"x")

    provider = MagicMock()
    provider.generate_structured.return_value = {
        "vlm": {"category": "家居/工艺品", "appearance": "x", "key_features": ["a", "b", "c"]},
        "douyin": {"title": "t", "subtitle": "s", "selling_points": ["1","2","3"], "description_md": "d", "category_path": "x", "keywords": ["k1","k2","k3","k4","k5"]},
        "shipinhao": {"title": "t", "subtitle": "s", "selling_points": ["1","2","3"], "description_md": "d", "category_path": "x", "keywords": ["k1","k2","k3","k4","k5"]},
        "xiaohongshu": {"post_title": "p", "post_body": "b", "selling_points": ["1","2","3"], "hashtags": ["#a","#b","#c","#d","#e"]},
    }

    result = generate_copy_for_sku(
        provider=provider,
        image_path=img,
        sku_name="蓝色布艺猫",
        scene_name="大理石台·暖光",
        scene_category="美妆/食品",
    )
    provider.generate_structured.assert_called_once()
    call = provider.generate_structured.call_args
    assert call.kwargs["image_path"] == img
    assert "蓝色布艺猫" in call.kwargs["prompt"]
    assert call.kwargs["json_schema"] == COPY_OUTPUT_SCHEMA
    assert "vlm" in result
    assert "douyin" in result
