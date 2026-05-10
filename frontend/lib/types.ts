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
}

export type ImageStatus = "pending" | "cutting" | "generating" | "composing" | "done" | "failed";

export interface SourceImage {
  id: string;
  name: string;
  src_path: string;
  status: ImageStatus;
  progress: number;
  err_msg: string | null;
  master_paths: Record<string, string>;
  derived_paths: Record<string, string>;
}

export type SKUStatus = "draft" | "ready" | "running" | "done" | "error";

export interface SKU {
  id: string;
  project_id: string;
  scene_id: string | null;
  name: string;
  status: SKUStatus;
  images: SourceImage[];
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
}
