"use client";
import { useState } from "react";
import type { Scene } from "@/lib/types";
import { Lightbox } from "./Lightbox";

const SOURCE_LABEL: Record<string, { text: string; cls: string }> = {
  system: { text: "系统", cls: "bg-zinc-700 text-zinc-200" },
  user: { text: "我的", cls: "bg-blue-700/70 text-blue-100" },
  ai_keywords: { text: "AI·关键词", cls: "bg-purple-700/70 text-purple-100" },
  ai_reference: { text: "AI·反推", cls: "bg-fuchsia-700/70 text-fuchsia-100" },
};

export function SceneCard({
  scene, onClick, onDelete,
}: {
  scene: Scene;
  onClick?: () => void;
  onDelete?: () => void;
}) {
  const fest = scene.festival || "通用";
  const src = SOURCE_LABEL[scene.created_by || "user"] || SOURCE_LABEL.user;
  const [zoom, setZoom] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const openInfo = (e: React.MouseEvent) => { e.stopPropagation(); onClick?.(); };
  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (deleting) return;
    if (!confirm(`确认删除模板「${scene.name}」？\n该操作不可撤销。`)) return;
    setDeleting(true);
    try { await onDelete?.(); } finally { setDeleting(false); }
  };
  const isGenerating = scene.category.includes("生成中");
  const isFailed = scene.category.includes("失败");
  return (
    <div className={`bg-zinc-900 border rounded-xl p-2 transition ${
      isGenerating ? "border-amber-600/60 animate-pulse"
      : isFailed ? "border-red-700/60"
      : "border-zinc-700 hover:border-blue-500"}`}>
      <div className="w-full aspect-[4/3] rounded mb-2 relative overflow-hidden bg-zinc-800 group">
        {scene.cover_url ? (
          <button
            onClick={() => setZoom(true)}
            className="block w-full h-full cursor-zoom-in"
            title="点击放大查看"
          >
            <img
              src={scene.cover_url}
              alt={scene.name}
              className="w-full h-full object-contain"
            />
          </button>
        ) : isGenerating ? (
          <div className="w-full h-full bg-gradient-to-br from-amber-900/30 to-zinc-900 flex flex-col items-center justify-center gap-1 text-[11px]">
            <span className="text-2xl">⏳</span>
            <span className="opacity-80">AI 生成中…</span>
            <span className="opacity-50 text-[9px]">约 1-2 分钟</span>
          </div>
        ) : (
          <button
            onClick={openInfo}
            className="w-full h-full bg-gradient-to-br from-zinc-700 to-zinc-900 flex items-center justify-center text-[10px] opacity-50 cursor-pointer"
            title="查看 prompt / 编辑模板"
          >
            无代表图（点击编辑）
          </button>
        )}
        <span className="absolute top-1.5 left-1.5 bg-black/65 text-white text-[10px] px-1.5 py-0.5 rounded pointer-events-none">
          {fest}
        </span>
        <span className={`absolute top-1.5 right-1.5 text-[9px] px-1.5 py-0.5 rounded pointer-events-none ${src.cls}`}>
          {src.text}
        </span>
        {/* 右下操作组：ⓘ 查看 / 🗑 删除 */}
        <div className="absolute bottom-1.5 right-1.5 flex gap-1">
          <button
            onClick={openInfo}
            className="w-6 h-6 rounded-full bg-black/70 hover:bg-blue-600 text-white text-xs flex items-center justify-center transition"
            title="查看 prompt / 编辑模板"
          >ⓘ</button>
          {onDelete && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="w-6 h-6 rounded-full bg-black/70 hover:bg-red-600 text-white text-xs flex items-center justify-center transition disabled:opacity-40"
              title="删除模板（需确认）"
            >{deleting ? "…" : "🗑"}</button>
          )}
        </div>
      </div>
      <h3 className="text-xs font-semibold cursor-pointer hover:underline" onClick={openInfo}>{scene.name}</h3>
      <p className="text-[10px] opacity-55 line-clamp-2">{scene.desc || scene.prompt.slice(0, 60)}</p>
      <p className="text-[9px] opacity-40 mt-0.5">{scene.category}</p>
      {zoom && scene.cover_url && (
        <Lightbox src={scene.cover_url} alt={scene.name} onClose={() => setZoom(false)} />
      )}
    </div>
  );
}
