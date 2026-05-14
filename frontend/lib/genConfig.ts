"use client";
/** "本次生成"的临时配置 — 全部从 page.tsx 散落 useState 收到一个 reducer。
 *  reducer 是纯函数，可单测。
 *  通过 useGenConfig(sid) 自动用 localStorage 按 SKU 持久化（刷新可恢复）。 */
import { useEffect, useReducer } from "react";

export type SceneMode = "template" | "reference";

export interface ReferenceImage {
  path: string;      // 服务端绝对路径（processSku 时回传）
  url: string;       // /static/ai-previews/...
  name: string;      // 文件名（展示用）
}

export interface GenConfig {
  /** 场景来源：模板 or 参考图（二选一） */
  mode: SceneMode;
  /** 参考图（mode='reference' 时有效）；mode='template' 时仍可保留，便于切回 */
  referenceImage: ReferenceImage | null;
  /** 用户附加正面提示词（叠加到模板/参考图之上） */
  extraPrompt: string;
  /** 附加 prompt 权重 0..1 */
  extraWeight: number;
  /** 用户负面提示词 */
  extraNegativePrompt: string;
  /** 多选要生成的原图 id 集合；空 = 生成全部 */
  selectedImgIds: Set<string>;
  /** 生成时是否覆盖原版本（不开 v2） */
  overwriteVersion: boolean;
}

export const initialGenConfig: GenConfig = {
  mode: "template",
  referenceImage: null,
  extraPrompt: "",
  extraWeight: 0.5,
  extraNegativePrompt: "",
  selectedImgIds: new Set(),
  overwriteVersion: false,
};

export type GenConfigAction =
  | { type: "set_prompt"; value: string }
  | { type: "set_weight"; value: number }
  | { type: "set_negative"; value: string }
  | { type: "set_mode"; value: SceneMode }
  | { type: "set_reference"; value: ReferenceImage | null }
  | { type: "select_imgs"; value: Set<string> }
  | { type: "toggle_img"; id: string }
  | { type: "select_all"; ids: string[] }
  | { type: "clear_selection" }
  | { type: "set_overwrite"; value: boolean }
  | { type: "hydrate"; value: GenConfig }
  | { type: "reset" };

export function genConfigReducer(state: GenConfig, action: GenConfigAction): GenConfig {
  switch (action.type) {
    case "set_prompt": return { ...state, extraPrompt: action.value };
    case "set_weight": return { ...state, extraWeight: action.value };
    case "set_negative": return { ...state, extraNegativePrompt: action.value };
    case "set_mode": return { ...state, mode: action.value };
    case "set_reference": return { ...state, referenceImage: action.value };
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
    case "hydrate": return action.value;
    case "reset": return initialGenConfig;
    default: return state;
  }
}

/** 派生：把 GenConfig 转成 processSku 的额外参数。
 *  - mode='reference' 且有图 → 走参考图分支（disableScene 隐式 true，referencePath 传过去）
 *  - mode='template' 但 useTemplate 被禁用历史 → disableScene=false (按 mode 走)
 *  返回 undefined 表示无任何额外参数（即"全默认模板"）。 */
export function toProcessExtra(c: GenConfig): {
  prompt: string; weight: number; negative: string;
  disableScene: boolean;
  referencePath: string | null;
} | undefined {
  const hasReference = c.mode === "reference" && c.referenceImage !== null;
  const disableScene = c.mode === "reference";  // 参考图模式即"停模板"
  const hasExtra =
    c.extraPrompt.trim() ||
    c.extraNegativePrompt.trim() ||
    disableScene ||
    hasReference;
  if (!hasExtra) return undefined;
  return {
    prompt: c.extraPrompt.trim(),
    weight: c.extraWeight,
    negative: c.extraNegativePrompt.trim(),
    disableScene,
    referencePath: hasReference ? c.referenceImage!.path : null,
  };
}

// --- localStorage 持久化 ---

const LS_PREFIX = "img2ec:genConfig:";

interface SerializedConfig extends Omit<GenConfig, "selectedImgIds"> {
  selectedImgIds: string[];
}

function serialize(c: GenConfig): string {
  const out: SerializedConfig = { ...c, selectedImgIds: Array.from(c.selectedImgIds) };
  return JSON.stringify(out);
}

function deserialize(raw: string): GenConfig | null {
  try {
    const parsed = JSON.parse(raw) as SerializedConfig;
    // mode 字段在老版本里没有；默认 template，兼容老 localStorage
    const mode: SceneMode = parsed.mode === "reference" ? "reference" : "template";
    return {
      mode,
      referenceImage: parsed.referenceImage ?? null,
      extraPrompt: parsed.extraPrompt ?? "",
      extraWeight: typeof parsed.extraWeight === "number" ? parsed.extraWeight : 0.5,
      extraNegativePrompt: parsed.extraNegativePrompt ?? "",
      selectedImgIds: new Set(Array.isArray(parsed.selectedImgIds) ? parsed.selectedImgIds : []),
      overwriteVersion: !!parsed.overwriteVersion,
    };
  } catch {
    return null;
  }
}

/** 主 hook：传 sid 启用 localStorage 持久化；不传则纯内存。 */
export function useGenConfig(sid?: string) {
  const [state, dispatch] = useReducer(genConfigReducer, initialGenConfig);

  // 初始 hydrate（仅一次；依赖 sid）
  useEffect(() => {
    if (!sid || typeof window === "undefined") return;
    const raw = window.localStorage.getItem(LS_PREFIX + sid);
    if (!raw) return;
    const restored = deserialize(raw);
    if (restored) dispatch({ type: "hydrate", value: restored });
  }, [sid]);

  // 状态变化时写回 localStorage
  useEffect(() => {
    if (!sid || typeof window === "undefined") return;
    window.localStorage.setItem(LS_PREFIX + sid, serialize(state));
  }, [sid, state]);

  return [state, dispatch] as const;
}
