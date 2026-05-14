const BASE = "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listProjects: () => req<import("./types").Project[]>("/api/projects"),
  createProject: (payload: { name: string; desc?: string; copy_default_scenes?: boolean }) =>
    req<import("./types").Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  patchProject: (id: string, payload: { name?: string; desc?: string }) =>
    req<import("./types").Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProject: (id: string) => req<void>(`/api/projects/${id}`, { method: "DELETE" }),

  listScenes: (pid: string) => req<import("./types").Scene[]>(`/api/projects/${pid}/scenes`),
  createScene: (pid: string, payload: Partial<import("./types").Scene>) =>
    req<import("./types").Scene>(`/api/projects/${pid}/scenes`, { method: "POST", body: JSON.stringify(payload) }),
  updateScene: (pid: string, sid: string, payload: Partial<import("./types").Scene>) =>
    req<import("./types").Scene>(`/api/projects/${pid}/scenes/${sid}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteScene: (pid: string, sid: string) => req<void>(`/api/projects/${pid}/scenes/${sid}`, { method: "DELETE" }),
  importDefaultScenes: (pid: string) =>
    req<import("./types").Scene[]>(`/api/projects/${pid}/scenes/import-defaults`, { method: "POST" }),

  // AI 模板：关键词扩展（5–60s）—— 同步预览版
  aiExpandKeywords: (pid: string, body: { keywords: string[]; festival: string; style: string }) =>
    req<import("./types").AIPreview>(
      `/api/projects/${pid}/scenes-ai/expand-from-keywords`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  // AI 模板：关键词扩展（fire-and-forget，立即返回占位 scene_id）
  aiQueueKeywords: (pid: string, body: { keywords: string[]; festival: string; style: string }) =>
    req<{ scene_id: string; festival: string }>(
      `/api/projects/${pid}/scenes-ai/queue-from-keywords`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  // AI 模板：批量生成 N 个（占位立即返回，后台 8-15 分钟跑完）
  aiBatchGenerate: (pid: string, body: { festival: string; count?: number }) =>
    req<{ scene_ids: string[]; count: number; festival: string }>(
      `/api/projects/${pid}/scenes-ai/batch-generate`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  // AI 模板：参考图反推（5–60s + ~50s 出 cover ≈ 90s）
  aiExpandReference: async (pid: string, file: File, festival: string, style: string) => {
    const fd = new FormData();
    fd.append("reference", file);
    fd.append("festival", festival);
    fd.append("style", style);
    const res = await fetch(`/api/projects/${pid}/scenes-ai/expand-from-reference`, {
      method: "POST", body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<import("./types").AIPreview>;
  },

  listSkus: (pid: string) => req<import("./types").SKU[]>(`/api/projects/${pid}/skus`),
  getSku: (pid: string, sid: string) => req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}`),
  createSku: (pid: string, payload: { name: string; scene_id?: string | null }) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus`, { method: "POST", body: JSON.stringify(payload) }),
  uploadImage: async (pid: string, sid: string, file: File, variantId?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const qs = variantId ? `?variant_id=${encodeURIComponent(variantId)}` : "";
    const res = await fetch(`/api/projects/${pid}/skus/${sid}/images${qs}`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<import("./types").SKU>;
  },
  createVariant: (pid: string, sid: string, color_name: string) =>
    req<{ id: string; color_name: string; status: string }>(
      `/api/projects/${pid}/skus/${sid}/variants`,
      { method: "POST", body: JSON.stringify({ color_name }) }
    ),
  renameVariant: (pid: string, sid: string, vid: string, color_name: string) =>
    req<{ id: string; color_name: string; status: string }>(
      `/api/projects/${pid}/skus/${sid}/variants/${vid}`,
      { method: "PATCH", body: JSON.stringify({ color_name }) }
    ),
  deleteVariant: (pid: string, sid: string, vid: string) =>
    req<void>(`/api/projects/${pid}/skus/${sid}/variants/${vid}`, { method: "DELETE" }),
  setVariantThumbnails: (pid: string, sid: string, vid: string, image_keys: string[]) =>
    req<{ id: string; sku_thumb_paths: string[]; sku_thumb_path: string | null }>(
      `/api/projects/${pid}/skus/${sid}/variants/${vid}/thumbnail`,
      { method: "POST", body: JSON.stringify({ image_keys }) }
    ),
  deleteImage: (pid: string, sid: string, iid: string) =>
    req<void>(`/api/projects/${pid}/skus/${sid}/images/${iid}`, { method: "DELETE" }),
  deleteMasterVersion: (
    pid: string, sid: string,
    body: { image_id: string; ratio: string; path: string },
  ) => req<import("./types").SKU>(
    `/api/projects/${pid}/skus/${sid}/master-versions/delete`,
    { method: "POST", body: JSON.stringify(body) },
  ),
  deleteDimensionImage: (
    pid: string, sid: string,
    body: { variant_id: string; style: string; image_idx: number },
  ) => req<import("./types").SKU>(
    `/api/projects/${pid}/skus/${sid}/dimension/delete`,
    { method: "POST", body: JSON.stringify(body) },
  ),
  // 批删该原图全部 master 版本（含历史）+ 清派生
  deleteAllMastersForImage: (pid: string, sid: string, iid: string) =>
    req<import("./types").SKU>(
      `/api/projects/${pid}/skus/${sid}/images/${iid}/delete-all-masters`,
      { method: "POST" },
    ),
  // 批删变体全部尺寸图
  deleteAllDimension: (pid: string, sid: string, variantId: string) =>
    req<import("./types").SKU>(
      `/api/projects/${pid}/skus/${sid}/dimension/delete-all?variant_id=${encodeURIComponent(variantId)}`,
      { method: "POST" },
    ),
  // 重新生成某张原图的所有规格（背后 process_image_task）
  regenerateImage: (
    pid: string, sid: string, iid: string,
    body?: { ratios?: string[]; extra_prompt?: string; extra_weight?: number },
  ) => req<{ queued: number; skipped_in_flight: number }>(
    `/api/projects/${pid}/skus/${sid}/images/${iid}/regenerate`,
    { method: "POST", body: body ? JSON.stringify(body) : undefined },
  ),
  processSku: (
    pid: string, sid: string,
    ratios?: string[], variantId?: string,
    extra?: {
      prompt: string; weight: number; negative?: string;
      disableScene?: boolean; referencePath?: string | null;
    },
    imageIds?: string[],
  ) => {
    const qs = variantId ? `?variant_id=${encodeURIComponent(variantId)}` : "";
    const body: any = {};
    if (ratios) body.ratios = ratios;
    if (extra && extra.prompt.trim()) {
      body.extra_prompt = extra.prompt;
      body.extra_weight = extra.weight;
    }
    if (extra && extra.negative && extra.negative.trim()) {
      body.extra_negative_prompt = extra.negative;
    }
    if (extra && extra.disableScene) body.disable_scene = true;
    if (extra && extra.referencePath) body.reference_image_path = extra.referencePath;
    if (imageIds && imageIds.length > 0) body.image_ids = imageIds;
    return req<{ queued: number }>(`/api/projects/${pid}/skus/${sid}/process${qs}`, {
      method: "POST",
      body: Object.keys(body).length ? JSON.stringify(body) : undefined,
    });
  },
  uploadReferenceImage: async (pid: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/projects/${pid}/uploads/reference`, {
      method: "POST", body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ path: string; url: string; name: string; size: number }>;
  },
  patchImage: (pid: string, sid: string, iid: string, body: { scene_id: string | null }) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}/images/${iid}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  patchSku: (pid: string, sid: string, body: { scene_id?: string | null; clear_scene?: boolean; name?: string }) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  previewPrompt: (
    pid: string, sid: string,
    extraPrompt = "", extraWeight = 0,
    extraNegativePrompt = "", disableScene = false,
    hasReference = false,
  ) => {
    const qs = new URLSearchParams();
    if (extraPrompt) {
      qs.set("extra_prompt", extraPrompt);
      qs.set("extra_weight", String(extraWeight));
    }
    if (extraNegativePrompt) qs.set("extra_negative_prompt", extraNegativePrompt);
    if (disableScene) qs.set("disable_scene", "true");
    if (hasReference) qs.set("has_reference", "true");
    const url = `/api/projects/${pid}/skus/${sid}/preview-prompt${qs.toString() ? "?" + qs.toString() : ""}`;
    return req<{ scene_name: string; scene_prompt: string; negative_prompt: string; per_ratio: Record<string,string> }>(url);
  },
  cancelSku: (pid: string, sid: string) =>
    req<{ ok: boolean }>(`/api/projects/${pid}/skus/${sid}/cancel`, { method: "POST" }),
  deleteSku: (pid: string, sid: string) => req<void>(`/api/projects/${pid}/skus/${sid}`, { method: "DELETE" }),
  updateDimensions: (pid: string, sid: string, dims: { length_cm: number | null; width_cm: number | null; height_cm: number | null }) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}/dimensions`, { method: "PATCH", body: JSON.stringify(dims) }),
  regenerateDimension: (pid: string, sid: string, styles: string[], variantId?: string, imageIndices?: number[]) => {
    const qs = variantId ? `?variant_id=${encodeURIComponent(variantId)}` : "";
    const body: any = { styles };
    if (imageIndices && imageIndices.length > 0) body.image_indices = imageIndices;
    return req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}/dimension/regenerate${qs}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  applyDimensionToDetail: (pid: string, sid: string, vid: string, style: "white" | "template") =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}/variants/${vid}/dimension/apply-to-detail`, {
      method: "POST",
      body: JSON.stringify({ style }),
    }),
  composeDetail: (pid: string, sid: string, vid: string, image_keys: string[]) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}/variants/${vid}/detail/compose`, {
      method: "POST",
      body: JSON.stringify({ image_keys }),
    }),

  reveal: (path: string) => req<void>("/api/fs/reveal", { method: "POST", body: JSON.stringify({ path }) }),
  downloadSku: (sid: string) => `/api/skus/${sid}/download`,
  downloadProjectAll: (pid: string) => `/api/projects/${pid}/download-all`,
  downloadBundle: async (
    pid: string, sid: string,
    body: { platform: string; variant_id: string; main_keys: string[]; detail_keys: string[] },
  ) => _downloadZipPOST(`/api/projects/${pid}/skus/${sid}/download-bundle`, body, `bundle-${sid}.zip`),
  downloadBundleAll: async (
    pid: string, sid: string,
    body: { variant_id: string; main_keys: string[]; detail_keys: string[] },
  ) => _downloadZipPOST(`/api/projects/${pid}/skus/${sid}/download-bundle-all`, body, `bundle-all-${sid}.zip`),
  getConcurrency: () => req<{ current: number | null; min: number; max: number }>(`/api/concurrency`),
  setConcurrency: (count: number) =>
    req<{ current: number; previous?: number; delta: number }>(`/api/concurrency`, {
      method: "POST", body: JSON.stringify({ count }),
    }),

  listCopy: (pid: string, sid: string, vid: string) =>
    req<import("./types").PlatformCopy[]>(
      `/api/projects/${pid}/skus/${sid}/variants/${vid}/copy`,
    ),
  regenerateCopy: (pid: string, sid: string, vid: string) =>
    req<import("./types").PlatformCopy[]>(
      `/api/projects/${pid}/skus/${sid}/variants/${vid}/copy/regenerate`,
      { method: "POST" },
    ),
};

async function _downloadZipPOST(url: string, body: any, fallbackName: string) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try { const j = await res.json(); detail = j.detail || detail; }
    catch { detail = await res.text() || detail; }
    throw new Error(`下载失败：${detail}`);
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  // 优先 RFC 5987 UTF-8 文件名
  let filename = fallbackName;
  const m5987 = cd.match(/filename\*=UTF-8''([^;]+)/i);
  if (m5987) filename = decodeURIComponent(m5987[1]);
  else {
    const m = cd.match(/filename="([^"]+)"/);
    if (m) filename = m[1];
  }
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl; a.download = filename;
  document.body.appendChild(a); a.click();
  a.remove(); URL.revokeObjectURL(objUrl);
}
