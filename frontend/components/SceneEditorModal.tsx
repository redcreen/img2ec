"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";

export function SceneEditorModal({
  pid, scene, onClose, onSaved,
}: { pid: string; scene: Scene | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: "", category: "自定义", desc: "", prompt: "", negative_prompt: "",
    ip_adapter_weight: 60, base_model: "flux-dev-fp8",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (scene) setForm({ ...form,
      name: scene.name, category: scene.category, desc: scene.desc,
      prompt: scene.prompt, negative_prompt: scene.negative_prompt,
      ip_adapter_weight: scene.ip_adapter_weight, base_model: scene.base_model,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene]);

  const submit = async () => {
    if (!form.name.trim() || !form.prompt.trim()) return setErr("模板名和 prompt 必填");
    setBusy(true);
    try {
      if (scene) await api.updateScene(pid, scene.id, form);
      else await api.createScene(pid, form);
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!scene) return;
    if (!confirm(`确认删除模板"${scene.name}"？`)) return;
    await api.deleteScene(pid, scene.id);
    onSaved();
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[520px] max-w-[700px] max-h-[90vh] overflow-y-auto"
           onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">{scene ? "编辑模板" : "新建模板"}</h2>
        {[
          { k: "name", label: "模板名", type: "input" },
          { k: "category", label: "品类（标签）", type: "input" },
          { k: "desc", label: "用途说明", type: "input" },
          { k: "prompt", label: "主 Prompt（英文）", type: "textarea" },
          { k: "negative_prompt", label: "负面 Prompt（可选）", type: "textarea" },
        ].map(f => (
          <div key={f.k} className="mb-3">
            <label className="text-xs opacity-65 block mb-1">{f.label}</label>
            {f.type === "textarea" ? (
              <textarea value={(form as any)[f.k]} onChange={e => setForm({ ...form, [f.k]: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" rows={3} />
            ) : (
              <input value={(form as any)[f.k]} onChange={e => setForm({ ...form, [f.k]: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" />
            )}
          </div>
        ))}
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">IPAdapter 权重：{form.ip_adapter_weight}</label>
          <input type="range" min={0} max={100} value={form.ip_adapter_weight}
            onChange={e => setForm({ ...form, ip_adapter_weight: +e.target.value })} className="w-full" />
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end items-center">
          {scene && <button className="text-red-400 border border-red-400 px-3 py-1 rounded text-xs" onClick={del}>删除</button>}
          <div className="flex-1" />
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>{busy ? "保存中…" : "保存"}</button>
        </div>
      </div>
    </div>
  );
}
