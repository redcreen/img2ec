"""默认模板：先只保留 2 个高频通用模板。
代表图存在 backend/assets/scene_covers/<slug>.jpg，由 API 加 cover_url。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSeed:
    name: str
    category: str
    desc: str
    prompt: str
    negative_prompt: str
    cover_filename: str | None = None  # 文件名，相对 backend/assets/scene_covers/
    ip_adapter_weight: int = 60
    base_model: str = "flux-dev-fp8"


DEFAULT_SCENES: list[SceneSeed] = [
    SceneSeed(
        name="纯白底",
        category="通用·主图",
        desc="淘宝/天猫白底主图刚需，全品类通用",
        prompt=(
            "pure white (#FFFFFF) studio background, even soft front lighting, no harsh shadow, "
            "subtle natural contact shadow under the product, clean professional product photography, "
            "sharp focus, high resolution, no text, no logo, no watermark"
        ),
        negative_prompt="cluttered background, gradient, color cast, harsh shadow, watermark, text, logo",
        cover_filename="white-bg.jpg",
    ),
    SceneSeed(
        name="中式实木桌面·窗光",
        category="家居/工艺品/民俗",
        desc="中式工艺品、布艺/刺绣、文创、礼品类（如布艺老虎、香囊、刺绣摆件等）",
        prompt=(
            "Chinese-style interior product photography scene, foreground: polished walnut wood "
            "tabletop (鸡翅木 or 红木) with rich warm grain, empty placement area, midground: softly "
            "out-of-focus traditional Chinese wooden cabinet with brass handles or carved wooden chair, "
            "soft window daylight from side, background: hint of paper window or bamboo curtain, "
            "side detail: green leaves of a small potted plant at frame edge, warm interior light, "
            "premium Chinese mid-range home decor e-commerce photography aesthetic, shallow depth of "
            "field with foreground sharp, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=(
            "flat, abstract, single-color background, plastic, modern, harsh, oversaturated, "
            "watermark, text, logo, floating object"
        ),
        cover_filename="chinese-wood.jpg",
    ),
]
