"""Phase 2: 16 个国内电商常用场景，按品类分组。"""
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


# 通用·主图（2）
_GENERIC = [
    SceneSeed(
        name="纯白底主图",
        category="通用·主图",
        desc="淘宝/天猫白底主图刚需，所有品类",
        prompt="pure white background, even soft studio lighting, no shadow, clean product photography, sharp focus, professional",
        negative_prompt="shadow, gradient, color cast, cluttered",
    ),
    SceneSeed(
        name="浅灰渐变背景",
        category="通用·主图",
        desc="商务感主图，3C 数码常用",
        prompt="soft gradient gray studio background, gentle vignette, premium feel, professional product shot",
        negative_prompt="pattern, harsh shadow",
    ),
]

# 3C 数码（2）
_TECH = [
    SceneSeed(
        name="极简硬光台面",
        category="3C 数码",
        desc="科技/数码商品的高级感",
        prompt="minimalist dark surface, hard rim light, high contrast, premium tech product shot, dramatic shadows",
        negative_prompt="cluttered, warm tones",
    ),
    SceneSeed(
        name="灰色水泥台·冷光",
        category="3C/工具",
        desc="工业风、工具、电子产品",
        prompt="concrete surface, cool blue-gray side light, industrial minimal, modern, sharp lines",
        negative_prompt="warm tones, soft",
    ),
]

# 美妆/食品（2）
# Prompt 关键改进：明确前景表面 + 中景 + 背景三层结构，让 Codex 生成有纵深的真实场景
# 而不是抽象色块。商品后续会被 composite 在前景表面上 — 所以场景必须先有"可放东西的桌面"。
_BEAUTY = [
    SceneSeed(
        name="大理石台·暖光",
        category="美妆/食品",
        desc="美妆护肤、轻食、礼品类首选；通用度高，跨品类适配",
        prompt="interior product photography scene, foreground: polished white marble countertop (empty surface where product will be placed), midground: softly out-of-focus warm beige wall with subtle daylight gradient, background: warm window light filtering in from upper-left casting soft caustics, side detail: a few green leaves at frame edge for life, depth of field with foreground sharp and background blurred, premium e-commerce photography aesthetic, no product visible, no text",
        negative_prompt="floating background, abstract texture only, harsh light, oversaturated, low quality, watermark, text, logo",
    ),
    SceneSeed(
        name="亚麻布料背景",
        category="美妆/家居",
        desc="天然质感商品（精油/手作）",
        prompt="interior scene, foreground: a piece of natural beige linen fabric loosely draped over a wooden surface providing a clean placement area, midground: softly blurred warm tones, background: window light from the side, organic earthy feel, no product, no text",
        negative_prompt="plastic, synthetic, glossy, harsh, watermark",
    ),
]

# 食品/家居（2）
_HOME = [
    SceneSeed(
        name="原木桌面·晨光",
        category="食品/家居",
        desc="食品、餐具、家居小物",
        prompt="interior scene, foreground: oak wood table surface with visible warm grain (empty area for product), midground: softly blurred sunlit window with sheer curtain, background: cream wall, side: small green plant peeking in, morning light side-cast, no product, no text",
        negative_prompt="dark, shadow heavy, cluttered, watermark",
    ),
    SceneSeed(
        name="中式实木桌面·窗光",
        category="家居/工艺品/民俗",
        desc="中式工艺品、布艺/刺绣摆件、文创、礼品类（如老虎布偶、香囊、刺绣摆件等）",
        prompt="Chinese-style interior product photography scene, foreground: polished walnut wood tabletop (鸡翅木 or 红木) with rich warm grain, empty placement area, midground: softly out-of-focus traditional Chinese wooden cabinet with brass handles or carved wooden chair, soft window daylight from side, background: hint of paper window or bamboo curtain, side detail: green leaves of a small potted plant at frame edge, warm interior light, premium Chinese mid-range home decor e-commerce photography aesthetic, shallow depth of field with foreground sharp, no product visible, no text, no logo, no watermark",
        negative_prompt="flat, abstract, single-color background, plastic, modern, harsh, oversaturated, watermark, text, logo, floating object",
    ),
]

# 户外/运动（1）
_OUTDOOR = [
    SceneSeed(
        name="户外草坪·自然光",
        category="户外/运动",
        desc="户外用品、运动器材、园艺",
        prompt="on green grass lawn, natural daylight, slight bokeh background, lifestyle outdoor, fresh and bright",
        negative_prompt="overcast, grey, dull",
    ),
]

# 服饰/夏季（1）
_SUMMER = [
    SceneSeed(
        name="海边沙滩·黄金时刻",
        category="服饰/夏季",
        desc="泳装、夏装、防晒、出行",
        prompt="beach sand at golden hour, ocean blur in background, summer vibe, warm sun, vibrant",
        negative_prompt="cloudy, dark, dull",
    ),
]

# 服饰/书（1）
_LIFESTYLE = [
    SceneSeed(
        name="咖啡厅一角",
        category="服饰/书",
        desc="服饰、包包、书籍、文创",
        prompt="cozy cafe corner, soft window light, warm wooden tones, slight bokeh, lifestyle composition",
        negative_prompt="crowded, dark, harsh",
    ),
]

# 服饰（2）
_FASHION = [
    SceneSeed(
        name="极简白墙·单衣架",
        category="服饰",
        desc="服饰挂拍主图",
        prompt="minimalist white wall, single hanger, soft side light, fashion editorial, clean composition",
        negative_prompt="cluttered, busy",
    ),
    SceneSeed(
        name="平铺穿搭",
        category="服饰",
        desc="服饰平铺图、配饰组合",
        prompt="flat lay clothing on neutral surface, top-down view, accessories arranged around, magazine style",
        negative_prompt="wrinkled, messy",
    ),
]

# 节日·大促（3）
_FESTIVE = [
    SceneSeed(
        name="双11促销红",
        category="节日·大促",
        desc="双11、618 大促主视觉",
        prompt="red festive background with gold accents, double 11 sale theme, celebration, premium feel",
        negative_prompt="pink, dull",
        ip_adapter_weight=65,
    ),
    SceneSeed(
        name="春节年货金红",
        category="节日·春节",
        desc="春节年货、礼盒",
        prompt="chinese new year theme, red and gold, subtle auspicious patterns, festive auspicious",
        negative_prompt="modern, cold",
        ip_adapter_weight=65,
    ),
    SceneSeed(
        name="七夕粉色浪漫",
        category="节日·情人节",
        desc="七夕、情人节、生日礼品",
        prompt="romantic pink rose tones, soft light, valentines theme, dreamy, gentle",
        negative_prompt="harsh, dark",
        ip_adapter_weight=65,
    ),
]

# 母婴（1）
_BABY = [
    SceneSeed(
        name="婴幼柔光场景",
        category="母婴",
        desc="母婴、玩具、儿童用品",
        prompt="soft pastel background, baby room aesthetic, gentle warm light, safe feel, cozy",
        negative_prompt="sharp, dark, harsh",
    ),
]

DEFAULT_SCENES: list[SceneSeed] = (
    _GENERIC + _TECH + _BEAUTY + _HOME + _OUTDOOR + _SUMMER + _LIFESTYLE + _FASHION + _FESTIVE + _BABY
)
