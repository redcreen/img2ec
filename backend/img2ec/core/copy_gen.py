"""SKU 文案生成：单次 Codex CLI 调用，VLM + 3 平台字段一次出。"""
from __future__ import annotations

from pathlib import Path

from img2ec.infra.llm_provider import LLMProvider

# 3 平台共享的字段约束（per spec §7.1，去掉淘宝、视频脚本）
TITLE_LIMITS = {
    "douyin": 60,
    "shipinhao": 30,
    "xiaohongshu": 20,
}

# Output schema: VLM 识别 + 3 平台各自字段
COPY_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "vlm": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "appearance": {"type": "string"},
                "key_features": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["category", "appearance", "key_features"],
            "additionalProperties": False,
        },
        "douyin": {"$ref": "#/$defs/platform_full"},
        "shipinhao": {"$ref": "#/$defs/platform_full"},
        "xiaohongshu": {"$ref": "#/$defs/platform_xhs"},
    },
    "required": ["vlm", "douyin", "shipinhao", "xiaohongshu"],
    "additionalProperties": False,
    "$defs": {
        "platform_full": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "selling_points": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
                "description_md": {"type": "string"},
                "category_path": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 10},
            },
            "required": ["title", "subtitle", "selling_points", "description_md", "category_path", "keywords"],
            "additionalProperties": False,
        },
        "platform_xhs": {
            "type": "object",
            "properties": {
                "post_title": {"type": "string"},
                "post_body": {"type": "string"},
                "selling_points": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
                "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 10},
            },
            "required": ["post_title", "post_body", "selling_points", "hashtags"],
            "additionalProperties": False,
        },
    },
}


def _build_prompt(*, sku_name: str, scene_name: str, scene_category: str) -> str:
    return f"""你是国内电商运营文案专家。看这张商品图，识别商品类目+外观+特征，然后为下列 3 个平台生成上架文案。

【SKU 名】{sku_name}
【场景】{scene_name}（类别：{scene_category}）

【输出严格按 JSON Schema】
1. vlm: 识别结果（中文）
   - category: 三级类目路径（家居/工艺品/布艺玩偶 这种）
   - appearance: 一句话描述外观
   - key_features: 3 条关键特征

2. douyin（抖店）：title ≤ {TITLE_LIMITS['douyin']} 字，subtitle，3-5 卖点，详情 markdown，category_path，5-10 keywords
3. shipinhao（视频号）：title ≤ {TITLE_LIMITS['shipinhao']} 字，其它同抖店
4. xiaohongshu（小红书）：post_title ≤ {TITLE_LIMITS['xiaohongshu']} 字（笔记标题），post_body 笔记正文，3-5 卖点，5-10 hashtags（带 # 号）

风格要求：
- 抖店/视频号偏卖货导向，强调卖点和性价比
- 小红书偏种草/分享，第一人称，emoji 轻量使用
- 中文，避免英文混杂
- 类目准确，符合平台分类常见路径"""


def generate_copy_for_sku(
    *,
    provider: LLMProvider,
    image_path: Path,
    sku_name: str,
    scene_name: str,
    scene_category: str,
    timeout: int = 180,
) -> dict:
    """调一次 Codex CLI，返回 vlm + 3 平台字段的全量 dict。"""
    prompt = _build_prompt(sku_name=sku_name, scene_name=scene_name, scene_category=scene_category)
    return provider.generate_structured(
        prompt=prompt,
        json_schema=COPY_OUTPUT_SCHEMA,
        image_path=image_path,
        timeout=timeout,
    )
