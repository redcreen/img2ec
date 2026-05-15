export interface Project {
  id: string;
  name: string;
  desc: string;
  root_path: string;
  sku_count: number;
  scene_count: number;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  project_id: string;
  name: string;
  category: string;
  desc: string;
  prompt: string;
  negative_prompt: string;
  ip_adapter_weight: number;
  base_model: string;
  cover_url: string | null;
  festival?: string;
  created_by?: string;
}

export const FESTIVALS = ["通用", "春节", "元宵", "端午", "七夕", "中秋", "重阳", "腊八"] as const;
export type Festival = (typeof FESTIVALS)[number];

export interface AIPreview {
  name: string;
  desc: string;
  prompt: string;
  prompt_zh: string;
  negative_prompt: string;
  festival: string;
  cover_path: string;
  cover_url: string;
  raw_text: string;
}

export type ImageStatus = "ready" | "pending" | "cutting" | "generating" | "composing" | "done" | "failed";

export interface SourceImage {
  id: string;
  name: string;
  src_path: string;
  status: ImageStatus;
  progress: number;
  err_msg: string | null;
  master_paths: Record<string, string>;
  derived_paths: Record<string, string>;
  src_url: string | null;
  master_urls: Record<string, string>;
  master_history_urls?: Record<string, Array<{ path: string; url: string }>>;  // 多版本
  derived_urls: Record<string, string>;
  pending_ratios?: string[];  // 当前在排队/在跑的 ratio（Redis 跨进程视图）
  scene_id?: string | null;   // per-image 模板覆盖；null 走 SKU 默认
}

export type SKUStatus = "draft" | "ready" | "running" | "done" | "error" | "cancelled";

export interface Variant {
  id: string;
  color_name: string;
  status: SKUStatus;
  // 每变体模板覆盖；null = 继承 SKU.scene_id
  scene_id: string | null;
  // 主色卡（兼容 = sku_thumb_paths[0]）
  sku_thumb_path: string | null;
  sku_thumb_url: string | null;
  // 多候选色卡（有序）
  sku_thumb_paths: string[];
  sku_thumb_urls: string[];
  images: SourceImage[];
  dimension_urls: Record<string, string>;
  dimension_states: Record<string, { status: "idle" | "generating" | "error"; err: string | null }>;
  created_at: string;
  updated_at: string;
}

export interface SKU {
  id: string;
  project_id: string;
  scene_id: string | null;
  name: string;
  status: SKUStatus;
  variants: Variant[];
  // 兼容字段（聚合所有变体）
  images: SourceImage[];
  length_cm: number | null;
  width_cm: number | null;
  height_cm: number | null;
  // 兼容字段（取 default variant 的）
  dimension_urls: Record<string, string>;
  dimension_states: Record<string, { status: "idle" | "generating" | "error"; err: string | null }>;
  created_at: string;
  updated_at: string;
}

export interface PlatformCopy {
  id: string;
  platform: "douyin" | "shipinhao" | "xiaohongshu";
  title: string;
  subtitle: string;
  selling_points: string[];
  description_md: string;
  category_path: string;
  keywords: string[];
  hashtags: string[];
  video_script: string;
  detail_template_url: string | null;
}
