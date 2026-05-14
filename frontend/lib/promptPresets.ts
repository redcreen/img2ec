/** 每种 mode 下"附加提示词"模板预设。
 *  分两类：正向 + 负向。点击即把对应文本 append 到对应 textarea。 */
import type { SceneMode } from "@/lib/genConfig";

export interface PromptPreset {
  label: string;       // 按钮文字
  text: string;        // 插入的文本
  kind: "positive" | "negative";
}

const REFERENCE_PRESETS: PromptPreset[] = [
  {
    label: "产品摆位",
    kind: "positive",
    text: "把产品放在画面中央偏下、靠近前景桌面边缘；占画面约 40% 大小；产品正面略偏左 5°，保持轻微立体感。",
  },
  {
    label: "沿用参考图调性",
    kind: "positive",
    text: "沿用参考图的暖色调、浅景深与左上自然光方向；阴影柔化；中景道具刻意虚化。",
  },
  {
    label: "防色彩漂移",
    kind: "positive",
    text: "产品颜色、图案、刺绣纹理与原图完全一致；不要让场景光线改变产品本身的颜色或图案。",
  },
  {
    label: "禁参考图文字",
    kind: "positive",
    text: "只取参考图的氛围与场景；不要复制其中任何文字、品牌、海报排版或其它产品。",
  },
  {
    label: "禁干扰元素（负）",
    kind: "negative",
    text: "logo、文字、水印、海报排版、装饰边框、其他产品、人、手、动物、塑料感",
  },
];

const TEMPLATE_PRESETS: PromptPreset[] = [
  {
    label: "保留 logo",
    kind: "positive",
    text: "产品 logo / 标签不被遮挡或裁切；保持清晰可读。",
  },
  {
    label: "靠窗暖光",
    kind: "positive",
    text: "产品摆在桌面靠近窗户的位置，斜入暖光从左上方打下来，柔和拉长的阴影。",
  },
  {
    label: "细节高光",
    kind: "positive",
    text: "产品表面刺绣 / 纹理保留细节高光；不要过曝。",
  },
  {
    label: "禁文字水印（负）",
    kind: "negative",
    text: "文字、水印、品牌字样、装饰边框、低分辨率、塑料感",
  },
];

const NONE_PRESETS: PromptPreset[] = [
  {
    label: "中式新年红喜",
    kind: "positive",
    text: "新中式春节场景背景，红色丝绸桌布、金色烛台、模糊背景中的窗格剪影，暖色调高级感商业摄影。",
  },
  {
    label: "极简白底",
    kind: "positive",
    text: "纯白柔和渐变背景，柔光柔影，产品居中，电商主图标准构图。",
  },
  {
    label: "暖木桌窗光",
    kind: "positive",
    text: "暖色木质桌面前景，背景虚化的中式茶具与绿植，自然窗光从左侧斜入，浅景深。",
  },
  {
    label: "禁人禁手（负）",
    kind: "negative",
    text: "人、手、动物、文字、水印、logo、海报排版",
  },
];

export function getPresets(mode: SceneMode): PromptPreset[] {
  switch (mode) {
    case "reference": return REFERENCE_PRESETS;
    case "template":  return TEMPLATE_PRESETS;
    case "none":      return NONE_PRESETS;
  }
}

/** append 一段文本到现有 textarea 值（用换行隔开，避免拼到一行）。 */
export function appendPrompt(existing: string, addition: string): string {
  const trimmed = existing.trim();
  if (!trimmed) return addition;
  return trimmed + "\n" + addition;
}
