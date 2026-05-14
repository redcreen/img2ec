"use client";
/** "本次生成"的临时配置 — 全部从 page.tsx 散落 useState 收到一个 reducer。
 *  reducer 是纯函数，可单测。 */
import { useReducer } from "react";

export interface GenConfig {
  /** 用户附加正面提示词（叠加到模板上） */
  extraPrompt: string;
  /** 附加 prompt 权重 0..1 */
  extraWeight: number;
  /** 用户负面提示词 */
  extraNegativePrompt: string;
  /** 是否启用 SKU 模板（UI 层 toggle，不动 DB） */
  useTemplate: boolean;
  /** 多选要生成的原图 id 集合；空 = 生成全部 */
  selectedImgIds: Set<string>;
  /** 生成时是否覆盖原版本（不开 v2） */
  overwriteVersion: boolean;
}

export const initialGenConfig: GenConfig = {
  extraPrompt: "",
  extraWeight: 0.5,
  extraNegativePrompt: "",
  useTemplate: true,
  selectedImgIds: new Set(),
  overwriteVersion: false,
};

export type GenConfigAction =
  | { type: "set_prompt"; value: string }
  | { type: "set_weight"; value: number }
  | { type: "set_negative"; value: string }
  | { type: "set_use_template"; value: boolean }
  | { type: "select_imgs"; value: Set<string> }
  | { type: "toggle_img"; id: string }
  | { type: "select_all"; ids: string[] }
  | { type: "clear_selection" }
  | { type: "set_overwrite"; value: boolean }
  | { type: "reset" };

export function genConfigReducer(state: GenConfig, action: GenConfigAction): GenConfig {
  switch (action.type) {
    case "set_prompt": return { ...state, extraPrompt: action.value };
    case "set_weight": return { ...state, extraWeight: action.value };
    case "set_negative": return { ...state, extraNegativePrompt: action.value };
    case "set_use_template": return { ...state, useTemplate: action.value };
    case "select_imgs": return { ...state, selectedImgIds: action.value };
    case "toggle_img": {
      const next = new Set(state.selectedImgIds);
      if (next.has(action.id)) next.delete(action.id);
      else next.add(action.id);
      return { ...state, selectedImgIds: next };
    }
    case "select_all": return { ...state, selectedImgIds: new Set(action.ids) };
    case "clear_selection": return { ...state, selectedImgIds: new Set() };
    case "set_overwrite": return { ...state, overwriteVersion: action.value };
    case "reset": return initialGenConfig;
    default: return state;
  }
}

/** 派生：把 GenConfig 转成 processSku 的 extra 参数。 */
export function toProcessExtra(c: GenConfig): { prompt: string; weight: number; negative: string; disableScene: boolean } | undefined {
  const hasExtra = c.extraPrompt.trim() || c.extraNegativePrompt.trim() || !c.useTemplate;
  if (!hasExtra) return undefined;
  return {
    prompt: c.extraPrompt.trim(),
    weight: c.extraWeight,
    negative: c.extraNegativePrompt.trim(),
    disableScene: !c.useTemplate,
  };
}

export function useGenConfig() {
  return useReducer(genConfigReducer, initialGenConfig);
}
