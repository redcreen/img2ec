"use client";
/** "本次生成"的临时配置 — 全部从 page.tsx 散落 useState 收到一个 reducer。
 *  reducer 是纯函数，可单测。
 *  通过 useGenConfig(sid) 自动用 localStorage 按 SKU 持久化（刷新可恢复）。 */
import { useEffect, useReducer, useRef } from "react";

export type SceneMode = "template" | "reference" | "none";

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
  /** 内置提示词开关；false → 不加任何系统规则，仅发用户 extraPrompt */
  useBuiltinPrompt: boolean;
}

export const initialGenConfig: GenConfig = {
  mode: "template",
  referenceImage: null,
  extraPrompt: "",
  extraWeight: 0.5,
  extraNegativePrompt: "",
  selectedImgIds: new Set(),
  overwriteVersion: false,
  useBuiltinPrompt: true,
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
  | { type: "set_builtin_prompt"; value: boolean }
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
    case "set_builtin_prompt": return { ...state, useBuiltinPrompt: action.value };
    case "hydrate": return action.value;
    case "reset": return initialGenConfig;
    default: return state;
  }
}

/** 派生：把 GenConfig 转成 processSku 的额外参数。
 *  - mode='template': 走 SKU 模板；disableScene=false
 *  - mode='reference' + 有图: 走参考图驱动；disableScene 隐式 true + referencePath 传过去
 *  - mode='none': 不用模板也不用参考图；disableScene=true，仅 extra_prompt 兜底
 *  返回 undefined 表示无任何额外参数（即"全默认模板，extra 也没填"）。 */
export function toProcessExtra(c: GenConfig): {
  prompt: string; weight: number; negative: string;
  disableScene: boolean;
  referencePath: string | null;
  useBuiltinPrompt: boolean;
} | undefined {
  const hasReference = c.mode === "reference" && c.referenceImage !== null;
  const disableScene = c.mode !== "template";  // reference / none 都不要 SKU 模板
  const hasExtra =
    c.extraPrompt.trim() ||
    c.extraNegativePrompt.trim() ||
    disableScene ||
    hasReference ||
    !c.useBuiltinPrompt;
  if (!hasExtra) return undefined;
  return {
    prompt: c.extraPrompt.trim(),
    weight: c.extraWeight,
    negative: c.extraNegativePrompt.trim(),
    disableScene,
    referencePath: hasReference ? c.referenceImage!.path : null,
    useBuiltinPrompt: c.useBuiltinPrompt,
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
    const mode: SceneMode =
      parsed.mode === "reference" ? "reference"
      : parsed.mode === "none" ? "none"
      : "template";
    return {
      mode,
      referenceImage: parsed.referenceImage ?? null,
      extraPrompt: parsed.extraPrompt ?? "",
      extraWeight: typeof parsed.extraWeight === "number" ? parsed.extraWeight : 0.5,
      extraNegativePrompt: parsed.extraNegativePrompt ?? "",
      selectedImgIds: new Set(Array.isArray(parsed.selectedImgIds) ? parsed.selectedImgIds : []),
      overwriteVersion: !!parsed.overwriteVersion,
      useBuiltinPrompt: typeof parsed.useBuiltinPrompt === "boolean" ? parsed.useBuiltinPrompt : true,
    };
  } catch {
    return null;
  }
}

/** 主 hook：按 (sid, vid) 在 localStorage 持久化；任一为空则纯内存。
 *  - mode/reference/extraPrompt/selectedImgIds 在变体级隔离 — 不同颜色独立配置
 *  - 用 useReducer lazy initializer，第一次渲染就拿持久化值 —— 没有
 *    "先 initialGenConfig 再 hydrate" 的窗口（避免写 effect 抢先覆盖 localStorage）。 */
export function useGenConfig(sid?: string, vid?: string) {
  const lsKey = sid && vid ? `${LS_PREFIX}${sid}:${vid}` : null;
  const [state, dispatch] = useReducer(genConfigReducer, lsKey, (key) => {
    if (!key || typeof window === "undefined") return initialGenConfig;
    const raw = window.localStorage.getItem(key);
    if (!raw) return initialGenConfig;
    return deserialize(raw) ?? initialGenConfig;
  });

  // 切换 SKU 或 变体时重新 hydrate（lazy init 只在 mount 跑一次）
  const lastKeyRef = useRef(lsKey);
  useEffect(() => {
    if (lastKeyRef.current === lsKey) return;
    lastKeyRef.current = lsKey;
    if (!lsKey || typeof window === "undefined") {
      dispatch({ type: "reset" });
      return;
    }
    const raw = window.localStorage.getItem(lsKey);
    if (!raw) {
      dispatch({ type: "reset" });
      return;
    }
    const restored = deserialize(raw);
    dispatch({ type: "hydrate", value: restored ?? initialGenConfig });
  }, [lsKey]);

  // 状态变化时写回 localStorage
  useEffect(() => {
    if (!lsKey || typeof window === "undefined") return;
    window.localStorage.setItem(lsKey, serialize(state));
  }, [lsKey, state]);

  return [state, dispatch] as const;
}
