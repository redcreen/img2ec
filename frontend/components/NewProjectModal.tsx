"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export function NewProjectModal({
  onClose, onCreated,
}: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!name.trim()) return setErr("项目名必填");
    setBusy(true);
    try {
      // copy_default_scenes 走后端默认 (true) — 给一份起步模板库；
      // 模板/参考图/都不选三种模式下都可选；不再让用户在新建时关心
      await api.createProject({ name: name.trim(), desc: desc.trim() });
      onCreated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[440px] max-w-[600px]" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">新建项目</h2>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">项目名</label>
          <input value={name} onChange={e => setName(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm"
            placeholder="例如：双11促销" autoFocus />
        </div>
        <div className="mb-4">
          <label className="text-xs opacity-65 block mb-1">说明（可选）</label>
          <textarea value={desc} onChange={e => setDesc(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" rows={2} />
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>
            {busy ? "创建中…" : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}
