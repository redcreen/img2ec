"""默认模板：节庆挂件摆件向 30 个
（通用×6 / 春节×6 / 元宵×2 / 端午×6 / 七夕×2 / 中秋×4 / 重阳×2 / 腊八×2）。

每个模板对应 backend/assets/scene_covers/<cover_filename>，由 API 返回 cover_url。
cover 缺失时前端展示 fallback。covers 由 scripts/generate_seed_covers.py 用 Codex 一次性生成。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSeed:
    name: str
    category: str
    desc: str
    prompt: str
    negative_prompt: str
    cover_filename: str | None = None  # 相对 backend/assets/scene_covers/
    ip_adapter_weight: int = 60
    base_model: str = "flux-dev-fp8"
    festival: str = "通用"


_NEG_BASE = (
    "cluttered, plastic, modern industrial, harsh shadow, oversaturated, watermark, "
    "text, logo, floating object, fake AI gradient, low quality"
)


DEFAULT_SCENES: list[SceneSeed] = [
    # ============ 通用 × 6 ============
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
        festival="通用",
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
        festival="通用",
    ),
    SceneSeed(
        name="米白宣纸·留白",
        category="通用·新中式",
        desc="高级感留白底，适合所有新中式手作摆件、香囊、文创单品",
        prompt=(
            "soft warm-white traditional Chinese xuan paper textured background, very gentle "
            "fiber grain visible, subtle uneven cream-beige tone, faint shadow of bamboo leaf or "
            "ink wash mark at the corner, minimalist negative space, soft natural daylight from "
            "above, premium calm aesthetic, clean Chinese new-traditional e-commerce style, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="xuan-paper.jpg",
        festival="通用",
    ),
    SceneSeed(
        name="青砖墙·古朴",
        category="通用·古风",
        desc="古风/民俗摆件、福袋、香囊背景，质感强、辨识度高",
        prompt=(
            "weathered grey Chinese qingzhuan (青砖) brick wall textured background, slightly "
            "moss-touched grout lines, gentle warm side light raking across the surface revealing "
            "subtle brick relief, calm muted earthy palette, traditional Chinese architectural "
            "aesthetic, minimal foreground shelf hint, premium e-commerce photography style, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="qingzhuan-wall.jpg",
        festival="通用",
    ),
    SceneSeed(
        name="深色禅意·黑檀木",
        category="通用·禅意/高端",
        desc="高端礼品/茶器/沉香类调性，沉稳大气",
        prompt=(
            "dark ebony wood tabletop (黑檀木) with deep reddish-brown grain, soft directional warm "
            "light from upper left creating gentle highlight on the wood surface, blurred Chinese "
            "ink painting (山水画) hanging in dark background, very subtle smoke or incense haze, "
            "moody zen aesthetic, premium high-end e-commerce photography, shallow depth of field, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="ebony-zen.jpg",
        festival="通用",
    ),
    SceneSeed(
        name="禅意茶席·留香",
        category="通用·茶禅",
        desc="茶器/沉香/挂件类禅意背景，沉稳留白",
        prompt=(
            "minimalist Chinese tea-ceremony scene, foreground: weathered grey slate stone slab "
            "or beige hemp linen tea cloth with calm texture and empty placement area, midground: "
            "softly out-of-focus small purple-clay (紫砂) teapot and tea cups, hint of curling "
            "incense smoke (沉香) rising at the side, very subtle distant blurred bamboo or paper "
            "wall, gentle warm side daylight, refined zen aesthetic with deep negative space, "
            "premium calm e-commerce photography, shallow depth of field, no product visible, "
            "no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="tea-zen.jpg",
        festival="通用",
    ),

    # ============ 春节 × 6 ============
    SceneSeed(
        name="春节·红木桌·灯笼光",
        category="春节·主图",
        desc="春节挂件/摆件首选场景，喜庆暖色不俗气",
        prompt=(
            "Chinese New Year (春节) festive interior scene, foreground: polished rosewood (红木) "
            "tabletop with rich grain, midground: softly out-of-focus red Chinese lantern emitting "
            "warm golden glow, hint of red couplet (春联) on the wall, sprig of red plum blossom "
            "(梅花) in a Chinese porcelain vase at the side, warm festive lighting with golden "
            "highlights, premium new-traditional Chinese new year e-commerce aesthetic, shallow "
            "depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cny-rosewood-lantern.jpg",
        festival="春节",
    ),
    SceneSeed(
        name="春节·红绸缎面·金箔",
        category="春节·新中式",
        desc="高端礼盒类、福袋类商品；红金配色但有质感不土",
        prompt=(
            "elegant red silk satin (红绸) background with subtle vertical drape folds, faint "
            "gold leaf (金箔) flake accents scattered, soft top-left warm light catching the satin "
            "sheen, premium luxury Chinese New Year gift packaging aesthetic, smooth fabric texture, "
            "minimal empty placement area in foreground, refined new-traditional palette, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cny-red-silk.jpg",
        festival="春节",
    ),
    SceneSeed(
        name="春节·门神/福字·暖橘光",
        category="春节·民俗",
        desc="带门神/福字符号的民俗调，适合传统年味重的产品",
        prompt=(
            "traditional Chinese New Year doorway scene, softly out-of-focus red door with "
            "vertical golden 福 character couplet, warm orange-toned light spilling from the side "
            "as if at dusk, foreground: weathered stone threshold with empty placement area, "
            "muted festive palette with deep reds and warm gold, calm joyful aesthetic, "
            "premium Chinese folk-style e-commerce photography, shallow depth of field, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cny-fu-doorway.jpg",
        festival="春节",
    ),
    SceneSeed(
        name="春节·年宵花·红梅",
        category="春节·清新",
        desc="清新雅致的年节调，适合刺绣/香囊等女性向手作",
        prompt=(
            "fresh Chinese New Year (春节) scene, foreground: cream porcelain tabletop with empty "
            "placement area, midground: a branch of vivid red plum blossom (红梅) in a celadon "
            "(青瓷) vase, softly out-of-focus rice paper window letting in cool morning daylight, "
            "subtle red envelope (红包) and gold sycee accent at frame edge, refined elegant "
            "festive palette, premium boutique e-commerce photography, shallow depth of field, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cny-plum-celadon.jpg",
        festival="春节",
    ),
    SceneSeed(
        name="春节·八仙桌·瓜果茶",
        category="春节·民俗",
        desc="年俗居家氛围，适合摆件/挂件等小物",
        prompt=(
            "traditional Chinese New Year home scene, foreground: dark walnut bāxiān (八仙桌) "
            "square wooden tea table with calm grain, midground: small plate of red oranges (年橘) "
            "and a hand-painted blue-and-white teapot (青花茶壶) softly out of focus, hanging red "
            "tassels (红色穗子) at the upper-right corner of frame, warm interior daylight with "
            "subtle golden cast, festive but tasteful family living atmosphere, premium new-traditional "
            "e-commerce photography, shallow depth of field, no product visible, no text, no logo, "
            "no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cny-baxian-table.jpg",
        festival="春节",
    ),
    SceneSeed(
        name="元宵·花灯·汤圆",
        category="元宵·主图",
        desc="元宵节摆件挂件氛围，灯节暖意",
        prompt=(
            "Lantern Festival (元宵节) warm evening scene, foreground: warm walnut wood tabletop "
            "with empty placement area, midground: softly-blurred small bowl of glutinous rice "
            "balls (汤圆) in clear sweet soup, hint of glowing red paper lantern (花灯) hanging in "
            "the upper background casting soft warm golden light, faint silhouette of a riddle "
            "slip (灯谜) attached to lantern, festive but cozy family aesthetic, premium Chinese "
            "folk-festival e-commerce photography, shallow depth of field, no product visible, "
            "no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="lf-tangyuan-lantern.jpg",
        festival="元宵",
    ),
    SceneSeed(
        name="元宵·宫灯·夜雪",
        category="元宵·古风",
        desc="古风夜景，宫灯雪夜，礼盒摆件氛围片",
        prompt=(
            "ancient Chinese Lantern Festival night scene, foreground: dark polished wood ledge "
            "with calm empty placement surface dusted with subtle snow, midground: softly out-of-focus "
            "traditional palace lantern (宫灯) hanging with intricate carved silhouette, hint of "
            "gently falling snow flakes against the dark indigo night sky, distant red palace wall "
            "blurred in background, atmospheric moody premium Chinese e-commerce photography, "
            "shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="lf-gongdeng-snow.jpg",
        festival="元宵",
    ),
    SceneSeed(
        name="春节·墨色国潮·金红",
        category="春节·国潮",
        desc="年轻向国潮商品适用，配色大胆但克制",
        prompt=(
            "modern guo-chao (国潮) Chinese New Year aesthetic, deep ink-black background with "
            "subtle gold-leaf brushstroke calligraphy (墨与金) softly blurred, single rich red "
            "accent element (small red lantern or red string), strong dramatic side lighting, "
            "high contrast premium young-Chinese fashion e-commerce styling, modern but rooted "
            "in tradition, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cny-guochao-ink.jpg",
        festival="春节",
    ),

    # ============ 端午 × 6 ============
    SceneSeed(
        name="端午·艾草菖蒲·窗光",
        category="端午·民俗",
        desc="端午经典氛围，挂件/香囊/小老虎类直接出片",
        prompt=(
            "Dragon Boat Festival (端午节) traditional scene, foreground: warm walnut wood "
            "tabletop with empty placement area, midground: a small softly-blurred bunch of "
            "fresh artemisia (艾草) and calamus (菖蒲) leaves bound with red string, side: hint "
            "of glazed celadon teacup with a few zongzi rice dumplings (粽子) wrapped in green "
            "leaves out of focus, soft warm afternoon window light, premium Chinese folk-festival "
            "e-commerce aesthetic, shallow depth of field, no product visible, no text, no logo, "
            "no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="dw-aicao-changpu.jpg",
        festival="端午",
    ),
    SceneSeed(
        name="端午·五色丝线·麻布",
        category="端午·手作",
        desc="香囊/小老虎/平安结类布艺手作背景",
        prompt=(
            "Dragon Boat Festival (端午) handcraft scene, foreground: rough natural linen "
            "(粗麻布) tabletop with soft texture, midground: softly-out-of-focus five-color "
            "silk thread (五色丝线 in red, yellow, blue, white, black) coiled loosely, hint of "
            "dried artemisia bunch in a small bamboo basket at frame edge, warm side daylight, "
            "subtle handmade homemade aesthetic, premium folk-craft e-commerce photography, "
            "shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="dw-wuse-silk.jpg",
        festival="端午",
    ),
    SceneSeed(
        name="端午·粽叶·青瓷",
        category="端午·清新",
        desc="清新雅致端午调，适合中高端布艺/刺绣类",
        prompt=(
            "fresh Dragon Boat Festival (端午) scene, foreground: a single broad fresh bamboo "
            "leaf (粽叶) laid flat as a clean placement surface, midground: softly-blurred "
            "celadon (青瓷) bowl with a few zongzi out of focus, side: branch of fragrant sweet "
            "flag (菖蒲) reaching into the frame, cool clean morning daylight, refined elegant "
            "new-traditional Chinese aesthetic, premium boutique e-commerce photography, shallow "
            "depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="dw-zongye-celadon.jpg",
        festival="端午",
    ),
    SceneSeed(
        name="端午·小院青砖·盆栽",
        category="端午·古风",
        desc="生活气浓的端午场景，故事感强",
        prompt=(
            "Dragon Boat Festival traditional Chinese courtyard scene, foreground: aged grey "
            "qingzhuan (青砖) ground with subtle moss, midground: softly-blurred small clay pot "
            "of fresh artemisia leaves and a bundle of calamus stems at the doorstep, hint of "
            "wooden door frame with red string of garlic hanging out of focus, warm late-morning "
            "sunlight, calm folk life atmosphere, premium Chinese folk-festival e-commerce "
            "aesthetic, shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="dw-courtyard.jpg",
        festival="端午",
    ),
    SceneSeed(
        name="端午·龙舟剪影·暮光",
        category="端午·氛围",
        desc="赛龙舟意象，氛围片，礼盒类适用",
        prompt=(
            "Dragon Boat Festival evocative scene, foreground: dark polished wood tabletop "
            "with empty placement area, midground: softly out-of-focus silhouette of a "
            "traditional dragon boat (龙舟) on misty water, warm dusk light with deep orange "
            "and indigo sky, faint hint of red lantern reflection on the water, atmospheric "
            "premium e-commerce photography, shallow depth of field with foreground sharp, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="dw-longzhou-dusk.jpg",
        festival="端午",
    ),
    SceneSeed(
        name="端午·墨绿底·金线",
        category="端午·国潮",
        desc="年轻向国潮端午背景，色彩饱和有现代感",
        prompt=(
            "modern guo-chao (国潮) Dragon Boat Festival aesthetic, deep ink-green background "
            "with subtle hand-painted gold-thread wave pattern softly blurred, single bamboo leaf "
            "accent at the upper corner, single red silk thread accent, strong moody side "
            "lighting, high contrast premium young-Chinese fashion e-commerce styling, modern "
            "but rooted in folk tradition, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="dw-guochao-green.jpg",
        festival="端午",
    ),

    # ============ 七夕 × 2 ============
    SceneSeed(
        name="七夕·星河·乞巧",
        category="七夕·氛围",
        desc="情侣礼物/挂饰类七夕浪漫氛围",
        prompt=(
            "Qixi Festival (七夕) romantic night scene, foreground: pale grey-blue marble tabletop "
            "with subtle veining and empty placement area, midground: softly out-of-focus star-shaped "
            "candles and a faint silver thread spool (representing 乞巧 craft of stars), shimmering "
            "bokeh of soft fairy lights in deep indigo night sky background like a Milky Way (星河), "
            "gentle cool silvery moonlight rim-light, premium boutique romantic Chinese e-commerce "
            "aesthetic, shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="qx-galaxy.jpg",
        festival="七夕",
    ),
    SceneSeed(
        name="七夕·梅花鎏金·告白",
        category="七夕·新中式",
        desc="情侣礼盒/香囊类，新中式粉金浪漫调",
        prompt=(
            "Qixi Festival new-traditional Chinese romantic scene, foreground: soft cream porcelain "
            "tabletop with delicate gold-leaf trim and empty placement area, midground: softly-blurred "
            "single branch of pale pink plum blossom in a celadon vase, faint hint of folded red love "
            "letter at frame edge, warm golden side light catching subtle gold-leaf accents in the "
            "background, refined romantic premium Chinese e-commerce aesthetic with delicate restraint, "
            "shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="qx-pink-gold.jpg",
        festival="七夕",
    ),

    # ============ 中秋 × 4 ============
    SceneSeed(
        name="中秋·桂花·圆月",
        category="中秋·主图",
        desc="经典中秋夜氛围，礼盒类摆件类皆宜",
        prompt=(
            "Mid-Autumn Festival (中秋) night scene, foreground: walnut wood tabletop with "
            "calm grain, midground: softly out-of-focus cluster of yellow osmanthus (桂花) "
            "blossoms in a small ceramic bowl, hint of a bright full moon in the dark blue "
            "night sky background, faint silvery moonlight rim-lighting the foreground, warm "
            "candle accent at frame edge, calm festive premium Chinese new-traditional "
            "e-commerce aesthetic, shallow depth of field, no product visible, no text, no logo, "
            "no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="ma-osmanthus-moon.jpg",
        festival="中秋",
    ),
    SceneSeed(
        name="中秋·月饼·茶器",
        category="中秋·礼盒",
        desc="月饼礼盒/中秋茶器类商品的氛围背景",
        prompt=(
            "Mid-Autumn Festival tea-and-cake scene, foreground: dark rosewood tea tray with "
            "calm reflective surface and empty placement area, midground: softly-blurred stack "
            "of golden-glazed mooncakes (月饼) and a small purple-clay (紫砂) teapot, hint of "
            "warm tea steam, side: branch of osmanthus flowers in a celadon vase out of focus, "
            "warm evening lamp light from upper-left, premium Chinese gift-set e-commerce "
            "photography, shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="ma-mooncake-tea.jpg",
        festival="中秋",
    ),
    SceneSeed(
        name="中秋·墨蓝夜空·云月",
        category="中秋·氛围",
        desc="艺术感强的中秋夜氛围底，单品摆放显高级",
        prompt=(
            "Mid-Autumn Festival night-sky aesthetic, deep ink-blue background with subtle "
            "hand-painted wisps of cloud and a soft glowing full moon in the upper third, "
            "faint silvery rim-light, foreground: dark polished surface with calm empty "
            "placement area reflecting the moon faintly, traditional Chinese poetry mood, "
            "premium artistic e-commerce styling, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="ma-ink-night-moon.jpg",
        festival="中秋",
    ),
    SceneSeed(
        name="中秋·茶席·明月",
        category="中秋·礼盒",
        desc="茶器礼盒/月饼礼盒类茶席场景",
        prompt=(
            "Mid-Autumn Festival tea-ceremony scene, foreground: warm beige hemp linen tea cloth "
            "draped on dark walnut wood tea table with empty placement area, midground: softly "
            "out-of-focus rounded clay teapot and matching teacups arranged in a balanced triangle, "
            "hint of round osmanthus-flower-shaped mooncake on celadon plate, in the distance "
            "blurred soft glow of a full moon through a paper window screen, warm evening lamp "
            "light, refined premium Chinese gift-set e-commerce photography, shallow depth of field, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="ma-tea-fullmoon.jpg",
        festival="中秋",
    ),

    # ============ 重阳 × 2 ============
    SceneSeed(
        name="重阳·菊花·秋叶",
        category="重阳·主图",
        desc="重阳节挂件/摆件/茶礼，秋意菊花氛围",
        prompt=(
            "Double Ninth Festival (重阳) autumn scene, foreground: aged walnut wood tabletop with "
            "scattered fallen yellow ginkgo leaves and empty placement area, midground: softly "
            "out-of-focus cluster of yellow and white chrysanthemums (菊花) in a clay vase, hint "
            "of small porcelain bowl of warm chrysanthemum tea steaming gently at frame edge, "
            "warm golden afternoon side light, calm autumn premium Chinese e-commerce photography, "
            "shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cy-chrysanthemum.jpg",
        festival="重阳",
    ),
    SceneSeed(
        name="重阳·书房·登高远眺",
        category="重阳·古风",
        desc="重阳古风文房氛围，孝亲礼品类适合",
        prompt=(
            "Double Ninth Festival traditional Chinese scholar's study (书房) scene, foreground: "
            "warm rosewood desk with calm grain and empty placement area, midground: softly blurred "
            "open ancient classical Chinese book (古籍) and a brass paperweight, hint of yellow "
            "chrysanthemum branch in a celadon brush-washer at the side, soft warm autumn light "
            "filtering through a partially-open paper window with hint of distant mountain "
            "silhouette (登高), refined elegant premium Chinese new-traditional e-commerce aesthetic, "
            "shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="cy-scholar-study.jpg",
        festival="重阳",
    ),

    # ============ 腊八 × 2 ============
    SceneSeed(
        name="腊八·粥碗·谷物",
        category="腊八·主图",
        desc="腊八节温馨家居挂件/小礼品氛围",
        prompt=(
            "Laba Festival (腊八节) cozy winter scene, foreground: warm reddish-brown wood tabletop "
            "with scattered grains of millet, red beans and lotus seeds at the corner, empty "
            "placement area in front, midground: softly out-of-focus round ceramic bowl of warm "
            "Laba congee with steam gently rising, hint of small clay pots of dried grains at frame "
            "edge, warm interior lamp light with golden cast, calm homely premium Chinese e-commerce "
            "photography, shallow depth of field, no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="lb-congee.jpg",
        festival="腊八",
    ),
    SceneSeed(
        name="腊八·寒梅·雪窗",
        category="腊八·氛围",
        desc="冷调腊八氛围，腊梅+雪景，高级感单品适用",
        prompt=(
            "Laba Festival deep winter scene, foreground: cold grey stone window sill dusted with "
            "soft snow with empty placement area, midground: softly out-of-focus branch of bright "
            "yellow wintersweet (腊梅) blossom against blurred frosted paper window background, "
            "very subtle snowfall, gentle cool morning light, calm poetic Chinese new-traditional "
            "winter aesthetic, premium boutique e-commerce photography, shallow depth of field, "
            "no product visible, no text, no logo, no watermark"
        ),
        negative_prompt=_NEG_BASE,
        cover_filename="lb-lamei-snow.jpg",
        festival="腊八",
    ),
]
