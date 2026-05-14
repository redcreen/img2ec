"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Variant } from "@/lib/types";
import { StatusPill } from "./StatusPill";

export function VariantTabs({
  pid, sid, variants, activeId, onSelect, onChanged,
}: {
  pid: string;
  sid: string;
  variants: Variant[];
  activeId: string;
  onSelect: (vid: string) => void;
  onChanged: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const createVariant = async () => {
    const name = newName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const v = await api.createVariant(pid, sid, name);
      setNewName("");
      setCreating(false);
      // 等 SWR mutate 拿到新 variants 再切活动 id（否则 page useEffect 会把 active 重置回旧 default）
      await onChanged();
      onSelect(v.id);
    } catch (e: any) {
      alert("创建失败：" + e.message);
    } finally {
      setBusy(false);
    }
  };

  const renameVariant = async (v: Variant) => {
    const next = prompt(`重命名变体（当前：${v.color_name}）`, v.color_name);
    if (!next || next.trim() === v.color_name) return;
    try {
      await api.renameVariant(pid, sid, v.id, next.trim());
      onChanged();
    } catch (e: any) {
      alert("重命名失败：" + e.message);
    }
  };

  const deleteVariant = async (v: Variant) => {
    if (variants.length <= 1) {
      alert("不能删除唯一的变体");
      return;
    }
    if (!confirm(`删除变体「${v.color_name}」？图片不会被回收（手动清理），但变体记录会丢失。`)) return;
    try {
      await api.deleteVariant(pid, sid, v.id);
      if (activeId === v.id && variants.length > 1) {
        const other = variants.find((x) => x.id !== v.id);
        if (other) onSelect(other.id);
      }
      onChanged();
    } catch (e: any) {
      alert("删除失败：" + e.message);
    }
  };

  return (
    <div className="flex items-center gap-1 flex-wrap bg-zinc-900 border border-zinc-700 rounded-xl p-2">
      {variants.map((v) => {
        const isActive = v.id === activeId;
        return (
          <div
            key={v.id}
            className={`group relative flex items-center gap-1 px-3 py-1.5 rounded text-xs cursor-pointer transition ${
              isActive
                ? "bg-blue-600 text-white"
                : "bg-zinc-800 hover:bg-zinc-700 opacity-80 hover:opacity-100"
            }`}
            onClick={() => onSelect(v.id)}
          >
            {v.sku_thumb_url && (
              <img src={v.sku_thumb_url} alt="" className="w-5 h-5 rounded object-cover" />
            )}
            <span className="font-semibold">{v.color_name}</span>
            <StatusPill status={v.status as any} />
            {isActive && (
              <span className="ml-1 flex items-center gap-0.5">
                <button
                  onClick={(e) => { e.stopPropagation(); renameVariant(v); }}
                  className="text-[10px] opacity-70 hover:opacity-100 px-1"
                  title="重命名"
                >✎</button>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteVariant(v); }}
                  className="text-[10px] opacity-70 hover:opacity-100 px-1"
                  title="删除"
                >×</button>
              </span>
            )}
          </div>
        );
      })}

      {!creating ? (
        <button
          onClick={() => setCreating(true)}
          className="px-3 py-1.5 text-xs border border-dashed border-zinc-700 hover:border-blue-500 rounded opacity-70 hover:opacity-100"
        >+ 新增颜色</button>
      ) : (
        <div className="flex items-center gap-1 px-2 py-1 bg-zinc-800 rounded">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") createVariant(); if (e.key === "Escape") setCreating(false); }}
            placeholder="颜色名（如：蓝色）"
            className="bg-transparent text-xs outline-none w-28"
          />
          <button
            onClick={createVariant}
            disabled={busy || !newName.trim()}
            className="text-xs bg-blue-600 hover:bg-blue-500 px-2 py-0.5 rounded disabled:opacity-40"
          >✓</button>
          <button
            onClick={() => { setCreating(false); setNewName(""); }}
            className="text-xs opacity-70 hover:opacity-100 px-1"
          >×</button>
        </div>
      )}
    </div>
  );
}
