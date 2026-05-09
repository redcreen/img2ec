"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";

export function NewSkuModal({
  pid, scenes, onClose, onCreated,
}: { pid: string; scenes: Scene[]; onClose: () => void; onCreated: (sid: string) => void }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sceneId, setSceneId] = useState(scenes[0]?.id ?? "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) return setErr("SKU 名必填");
    if (!sceneId) return setErr("请选场景");
    if (files.length === 0) return setErr("请选至少一张原图");
    setBusy(true);
    try {
      const sku = await api.createSku(pid, { name: name.trim(), scene_id: sceneId });
      for (const f of files) {
        await api.uploadImage(pid, sku.id, f);
      }
      onCreated(sku.id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[520px] max-w-[700px]" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">新建 SKU</h2>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">SKU 名</label>
          <input value={name} onChange={e => setName(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" placeholder="例如：蓝色保温杯 500ml" autoFocus />
        </div>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">原图（可多张）</label>
          <input type="file" accept="image/*" multiple
            onChange={e => setFiles(Array.from(e.target.files || []))}
            className="text-xs" />
          {files.length > 0 && <p className="text-xs opacity-60 mt-1">{files.length} 张已选</p>}
        </div>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">场景</label>
          <select value={sceneId} onChange={e => setSceneId(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm">
            {scenes.map(sc => <option key={sc.id} value={sc.id}>{sc.name}（{sc.category}）</option>)}
          </select>
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>{busy ? "创建中…" : "创建并开始处理"}</button>
        </div>
      </div>
    </div>
  );
}
