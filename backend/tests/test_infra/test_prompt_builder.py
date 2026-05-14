"""build_master_prompt + format helpers — 纯函数全分支覆盖。"""
from img2ec.infra.prompt_builder import (
    CLOSEUP_KEYS,
    build_master_prompt,
    format_extra,
    format_negative,
)


# ---------- format_extra ----------

def test_format_extra_empty_returns_empty():
    assert format_extra("", 0.5) == ""
    assert format_extra("   ", 0.7) == ""


def test_format_extra_emphasis_buckets():
    # 0.0-0.24 → Light
    assert "Light preference" in format_extra("x", 0.2)
    # 0.25-0.54 → Moderate
    assert "Moderate emphasis" in format_extra("x", 0.4)
    # 0.55-0.84 → Strong
    assert "Strong emphasis" in format_extra("x", 0.7)
    # 0.85+ → HARD
    assert "HARD CONSTRAINT" in format_extra("x", 0.95)


def test_format_extra_clamps_weight():
    """weight 超出 0-1 应当被夹"""
    assert "weight=0.00" in format_extra("x", -5)
    assert "weight=1.00" in format_extra("x", 99)


def test_format_extra_preserves_user_text():
    out = format_extra("保留 logo", 0.5)
    assert "保留 logo" in out


# ---------- format_negative ----------

def test_format_negative_empty_returns_empty():
    assert format_negative("") == ""
    assert format_negative("   ") == ""


def test_format_negative_appends_constraints():
    out = format_negative("不要文字")
    assert "Additional negative constraints" in out
    assert "不要文字" in out


# ---------- build_master_prompt ----------

def test_build_with_scene_has_scene_line():
    p = build_master_prompt(scene_prompt="中式实木桌面", ratio_key="1x1")
    assert "Scene: 中式实木桌面" in p
    assert "1024x1024" in p
    assert "Critical rules" in p


def test_build_empty_scene_uses_pure_user_mode():
    p = build_master_prompt(scene_prompt="", ratio_key="1x1")
    assert "Scene:" not in p
    assert "defined entirely by the additional user instruction" in p


def test_build_empty_scene_with_extra_includes_user_section():
    p = build_master_prompt(scene_prompt="", ratio_key="1x1",
                            extra_prompt="偏暖光", extra_weight=0.8)
    assert "偏暖光" in p
    assert "Strong emphasis" in p


def test_build_with_negative_appends_after_extra():
    p = build_master_prompt(
        scene_prompt="any scene", ratio_key="1x1",
        extra_prompt="warm", extra_weight=0.5,
        extra_negative_prompt="no text",
    )
    # negative 应该在 extra 之后
    extra_idx = p.find("warm")
    neg_idx = p.find("Additional negative")
    assert extra_idx > 0 and neg_idx > 0
    assert neg_idx > extra_idx


def test_build_closeup_keys_use_pil_description():
    for key in CLOSEUP_KEYS:
        p = build_master_prompt(scene_prompt="ignored", ratio_key=key)
        # 特写图分支返回 PIL 说明，不含 Scene/Critical rules
        assert "[特写图]" in p
        assert "PIL" in p
        assert "Scene:" not in p
        assert "Critical rules" not in p


def test_build_ratio_keys_have_correct_size():
    for key, expected in [("1x1", "1024x1024"), ("long", "1024x1536"),
                           ("3x4", "1024x1536"), ("9x16", "1024x1792"),
                           ("16x9", "1792x1024")]:
        p = build_master_prompt(scene_prompt="x", ratio_key=key)
        assert expected in p, f"{key} should include {expected}"


def test_build_unknown_ratio_falls_back():
    """未知 ratio_key 不应崩，默认 1024x1024。"""
    p = build_master_prompt(scene_prompt="x", ratio_key="bogus")
    assert "1024x1024" in p


def test_build_preview_equals_actual_when_same_args():
    """preview_prompt endpoint 与 worker 调同函数 → 同输入 → 同输出。"""
    args = dict(scene_prompt="warm wood", ratio_key="1x1",
                extra_prompt="logo visible", extra_weight=0.6,
                extra_negative_prompt="no people")
    assert build_master_prompt(**args) == build_master_prompt(**args)


def test_build_reference_mode_ignores_scene():
    """has_reference=True 时即使 scene_prompt 非空也走参考图分支。"""
    p = build_master_prompt(
        scene_prompt="should be ignored",
        ratio_key="1x1",
        has_reference=True,
    )
    assert "TWO reference images" in p
    assert "should be ignored" not in p
    assert "PRODUCT to place" in p
    assert "SCENE REFERENCE" in p


def test_build_reference_mode_forbids_copying_ref_text():
    """参考图模式必须明确指出不要把参考图里的文字 / banner / 其他产品搬到输出。"""
    p = build_master_prompt(
        scene_prompt="",
        ratio_key="3x4",
        has_reference=True,
    )
    assert "NEVER copy text" in p or "do not copy" in p.lower() or "never copy" in p.lower()
    # 参考图模式仍走 extra/negative 兜底
    p2 = build_master_prompt(
        scene_prompt="", ratio_key="1x1", has_reference=True,
        extra_prompt="warm tone", extra_weight=0.5,
        extra_negative_prompt="no animals",
    )
    assert "warm tone" in p2
    assert "no animals" in p2
