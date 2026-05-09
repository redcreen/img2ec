"""MVP Phase 1：仅 1 个默认场景。Phase 2 再扩充到 16 个。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSeed:
    name: str
    category: str
    desc: str
    prompt: str
    negative_prompt: str
    ip_adapter_weight: int = 60
    base_model: str = "flux-dev-fp8"


DEFAULT_SCENES: list[SceneSeed] = [
    SceneSeed(
        name="大理石台·暖光",
        category="美妆/食品",
        desc="美妆护肤、轻食、礼品类首选；通用度高，跨品类适配",
        prompt=(
            "product on a white marble surface, warm soft window light from the left, "
            "45-degree camera angle, premium product photography, shallow depth of field, "
            "minimal composition, natural shadows"
        ),
        negative_prompt="cluttered, harsh light, oversaturated, low quality, watermark, text",
        ip_adapter_weight=60,
        base_model="flux-dev-fp8",
    ),
]
