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
  deleteProject: (id: string) => req<void>(`/api/projects/${id}`, { method: "DELETE" }),

  listScenes: (pid: string) => req<import("./types").Scene[]>(`/api/projects/${pid}/scenes`),
  createScene: (pid: string, payload: Partial<import("./types").Scene>) =>
    req<import("./types").Scene>(`/api/projects/${pid}/scenes`, { method: "POST", body: JSON.stringify(payload) }),
  updateScene: (pid: string, sid: string, payload: Partial<import("./types").Scene>) =>
    req<import("./types").Scene>(`/api/projects/${pid}/scenes/${sid}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteScene: (pid: string, sid: string) => req<void>(`/api/projects/${pid}/scenes/${sid}`, { method: "DELETE" }),

  listSkus: (pid: string) => req<import("./types").SKU[]>(`/api/projects/${pid}/skus`),
  getSku: (pid: string, sid: string) => req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}`),
  createSku: (pid: string, payload: { name: string; scene_id?: string | null }) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus`, { method: "POST", body: JSON.stringify(payload) }),
  uploadImage: async (pid: string, sid: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/projects/${pid}/skus/${sid}/images`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<import("./types").SKU>;
  },
  deleteImage: (pid: string, sid: string, iid: string) =>
    req<void>(`/api/projects/${pid}/skus/${sid}/images/${iid}`, { method: "DELETE" }),
  processSku: (pid: string, sid: string) =>
    req<{ queued: number }>(`/api/projects/${pid}/skus/${sid}/process`, { method: "POST" }),
  deleteSku: (pid: string, sid: string) => req<void>(`/api/projects/${pid}/skus/${sid}`, { method: "DELETE" }),

  reveal: (path: string) => req<void>("/api/fs/reveal", { method: "POST", body: JSON.stringify({ path }) }),
  downloadSku: (sid: string) => `/api/skus/${sid}/download`,
  downloadProjectAll: (pid: string) => `/api/projects/${pid}/download-all`,
  listCopy: (sid: string) => req<import("./types").PlatformCopy[]>(`/api/skus/${sid}/copy`),
  regenerateCopy: (sid: string) => req<import("./types").PlatformCopy[]>(`/api/skus/${sid}/copy/regenerate`, { method: "POST" }),
};
