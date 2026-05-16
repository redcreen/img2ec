"""Pure functions to compose the final prompt sent to Codex.

完全无副作用、无 I/O — 100% pytest 可覆盖。
"""
from __future__ import annotations


# Codex/gpt-image-1 supported native sizes — we ask in these so output isn't squished.
PROMPT_SIZE_HINT: dict[str, str] = {
    # 比例图（带场景）
    "1x1":  "1024x1024",
    "long": "1024x1536",
    "3x4":  "1024x1536",
    "9x16": "1024x1792",
    "16x9": "1792x1024",
    # 特写图（白底，多角度）
    "front":  "1024x1024",
    "side":   "1024x1024",
    "detail": "1024x1024",
}

TARGET_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1x1":  (1024, 1024),
    "long": (1024, 1536),
    "3x4":  (1024, 1536),
    "9x16": (1024, 1792),
    "16x9": (1792, 1024),
    "front":  (1024, 1024),
    "side":   (1024, 1024),
    "detail": (1024, 1024),
}

CLOSEUP_KEYS = {"front", "side", "detail"}


def format_extra(extra_prompt: str, weight: float) -> str:
    """把用户附加 prompt 按权重转成强调级别字符串，附加到 base prompt 后。"""
    txt = (extra_prompt or "").strip()
    if not txt:
        return ""
    w = max(0.0, min(1.0, float(weight or 0.0)))
    if w < 0.25:
        emphasis = "Light preference (apply if it does not conflict with the rules above)"
    elif w < 0.55:
        emphasis = "Moderate emphasis"
    elif w < 0.85:
        emphasis = "Strong emphasis"
    else:
        emphasis = "HARD CONSTRAINT (must satisfy)"
    return f"\n\nAdditional user instruction ({emphasis}, weight={w:.2f}): {txt}"


def format_negative(extra_negative_prompt: str) -> str:
    txt = (extra_negative_prompt or "").strip()
    if not txt:
        return ""
    return f"\n\nAdditional negative constraints (must NOT appear): {txt}"


def build_master_prompt(
    *,
    scene_prompt: str,
    ratio_key: str,
    extra_prompt: str = "",
    extra_weight: float = 0.0,
    extra_negative_prompt: str = "",
    has_reference: bool = False,
    use_builtin: bool = True,
) -> str:
    """组装传给 Codex 的完整 prompt。

    - has_reference=True → 参考图驱动模式（输入有第二张参考图；scene_prompt 即使
      非空也忽略，由参考图决定场景；模板和参考图二选一是 UI 约束）
    - scene_prompt 为空且无参考图 → 纯人工模式
    - ratio_key ∈ CLOSEUP_KEYS → 仅返回说明文本（实际由 PIL crop 实现）
    - extra_* → 附加用户诉求与负面约束
    - use_builtin=False → 跳过所有内置规则/模板/参考图脚手架，仅发用户
      extra_prompt（高级用户自己掌控全部 prompt；scene/reference 仍由 extra_refs
      作为图输入存在，只是文字层不引导）
    """
    size_hint = PROMPT_SIZE_HINT.get(ratio_key, "1024x1024")
    suffix = format_extra(extra_prompt, extra_weight)
    neg_suffix = format_negative(extra_negative_prompt)

    if ratio_key in CLOSEUP_KEYS:
        descriptions = {
            "front": "中央 70% 方形区裁剪放大（正面）",
            "side":  "中央偏右 60% 方形区裁剪放大（侧面）",
            "detail": "中央 35% 紧凑方形区裁剪放大（局部细节）",
        }
        return (
            f"[特写图] {descriptions.get(ratio_key, ratio_key)}\n"
            f"实现方式：PIL 从原图直接 crop + 放大（不调 Codex，不改图内容）。\n"
            f"输出尺寸：{size_hint} JPEG。"
        )

    # 内置提示词关闭：完全交给用户。仅追加 size hint 让 Codex 知道目标尺寸。
    if not use_builtin:
        user_text = (extra_prompt or "").strip()
        if not user_text:
            user_text = "Generate image based on the input image(s)."
        return f"{user_text}\n\nOutput: single {size_hint} JPEG." + neg_suffix

    if has_reference:
        # 参考图驱动：第一张 ref 是产品，第二张 ref 是场景参考图
        base = (
            f"You receive TWO reference images: "
            f"(A) the PRODUCT to place — preserve every embroidery detail, every stitch, "
            f"every color, every texture (pixel-fidelity for the product itself); "
            f"(B) the SCENE REFERENCE — match its composition framing, surface material, "
            f"prop arrangement, lighting direction, color temperature, depth-of-field and "
            f"overall aesthetic. "
            f"\n\nGoal: place the product (A) into a NEW scene that visually echoes the "
            f"reference (B). It does not have to be identical to (B); recreate the same "
            f"feel and stage."
            f"\n\nCritical rules: "
            f"(1) the product itself must remain visually identical to (A) — same shape, "
            f"same colors, same patterns, same orientation, same materials; "
            f"(2) NEVER copy text, banner, watermark, branding or other products from (B) "
            f"into the output — only its scene/lighting/aesthetic is referenced; "
            f"(3) natural shadow under product, ambient color reflections, contact shadow; "
            f"(4) absolutely NO text, NO watermark, NO additional duplicate products; "
            f"(5) output a single high-resolution {size_hint} photograph."
        )
        return base + suffix + neg_suffix

    scene_clean = (scene_prompt or "").strip()
    if not scene_clean:
        # 纯人工模式
        base = (
            f"Place this exact product (preserve every embroidery detail, every stitch, every color, "
            f"every texture — pixel-fidelity for the product itself) into a new {size_hint} scene "
            f"defined entirely by the additional user instruction below. "
            f"\n\nCritical rules: "
            f"(1) the product itself must remain visually identical to the input — same shape, "
            f"same colors, same patterns, same orientation, same materials; "
            f"(2) ONLY the surrounding scene/background changes; "
            f"(3) natural lighting and shadow consistent with the user-described scene; "
            f"(4) absolutely NO text, NO watermark, NO additional duplicate products in the frame; "
            f"(5) output a single high-resolution {size_hint} photograph."
        )
        return base + suffix + neg_suffix

    base = (
        f"Place this exact product (preserve every embroidery detail, every stitch, every color, "
        f"every texture — pixel-fidelity for the product itself) into a new {size_hint} scene. "
        f"\n\nScene: {scene_clean}\n\n"
        f"Critical rules: "
        f"(1) the product itself must remain visually identical to the input — same shape, "
        f"same colors, same patterns, same orientation, same materials; "
        f"(2) ONLY the surrounding scene/background changes; "
        f"(3) match the lighting direction and color temperature between product and new scene "
        f"(natural shadow under product, ambient color reflections, contact shadow); "
        f"(4) place the product on a believable surface with natural perspective; "
        f"(5) absolutely NO text, NO watermark, NO additional duplicate products in the frame; "
        f"(6) output a single high-resolution {size_hint} photograph."
    )
    return base + suffix + neg_suffix
