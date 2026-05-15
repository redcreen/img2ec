"use client";
import { useState } from "react";
import type { SourceImage } from "@/lib/types";
import { StatusPill } from "./StatusPill";

/** 原图卡列表：checkbox 多选、状态、进度条、× 删除、拖拽排序。
 *  拖拽用 native HTML5 DnD，左侧"⋮⋮"把手拖。drop 触发 onReorder(完整新顺序)。 */
const IN_FLIGHT = new Set(["pending", "cutting", "generating", "composing"]);

export function SourceImageList({
  images, selected, onToggleSelect, onSelectAll, onClearSelection,
  onDelete, onZoomSource, onReorder, skuCancelled = false,
}: {
  images: SourceImage[];
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onDelete: (iid: string, name: string) => void;
  onZoomSource: (img: SourceImage) => void;
  onReorder?: (orderedIds: string[]) => void;
  skuCancelled?: boolean;
}) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  const performReorder = (from: number, to: number) => {
    if (!onReorder) return;
    if (from === to || from < 0 || to < 0 || from >= images.length || to >= images.length) return;
    const ids = images.map((i) => i.id);
    const [moved] = ids.splice(from, 1);
    ids.splice(to, 0, moved);
    onReorder(ids);
  };

  if (images.length === 0) {
    return <p className="text-xs opacity-60">该变体还没上传原图 — 点右上"+ 添加"</p>;
  }
  return (
    <>
      <div className="flex items-center gap-2 mb-2 text-[11px] flex-wrap">
        <button
          onClick={onSelectAll}
          className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700"
        >全选</button>
        <button
          onClick={onClearSelection}
          className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700"
        >清空</button>
        <span className="opacity-60">
          已选 {selected.size}/{images.length}
          {selected.size === 0 && ' · 点击"▶ 生成"会处理全部'}
        </span>
        {onReorder && (
          <span className="opacity-50 ml-auto">⋮⋮ 拖拽左侧把手可调整顺序</span>
        )}
      </div>
      <div className="space-y-2 max-h-[480px] overflow-y-auto">
        {images.map((img, i) => {
          const isSelected = selected.has(img.id);
          const isDragging = dragFrom === i;
          const isDropTarget = dragOver === i && dragFrom !== null && dragFrom !== i;
          return (
            <div
              key={img.id}
              onDragOver={(e) => {
                if (!onReorder || dragFrom === null) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                setDragOver(i);
              }}
              onDragLeave={() => setDragOver((c) => (c === i ? null : c))}
              onDrop={(e) => {
                if (!onReorder) return;
                e.preventDefault();
                const from = parseInt(e.dataTransfer.getData("text/plain"));
                setDragOver(null);
                setDragFrom(null);
                if (!isNaN(from)) performReorder(from, i);
              }}
              className={`group bg-zinc-950 border rounded p-2 flex items-center gap-2 relative transition ${
                isDropTarget
                  ? "border-amber-400 ring-2 ring-amber-400/40"
                  : isSelected ? "border-blue-500" : "border-zinc-800"
              } ${isDragging ? "opacity-40" : ""}`}
            >
              {/* 拖拽把手 */}
              {onReorder && (
                <span
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", String(i));
                    setDragFrom(i);
                  }}
                  onDragEnd={() => { setDragFrom(null); setDragOver(null); }}
                  className="select-none text-zinc-500 hover:text-zinc-200 cursor-grab active:cursor-grabbing px-0.5 text-base flex-shrink-0"
                  title="拖动调整顺序"
                >⋮⋮</span>
              )}
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleSelect(img.id)}
                className="w-4 h-4 accent-blue-500 cursor-pointer flex-shrink-0"
                title="勾选后只生成选中的"
              />
              <span className="text-[10px] opacity-50 w-5 text-right flex-shrink-0">{i + 1}</span>
              {img.src_url ? (
                <img
                  src={img.src_url}
                  alt={img.name}
                  onClick={() => onZoomSource(img)}
                  className="w-20 h-20 object-cover rounded flex-shrink-0 cursor-zoom-in hover:opacity-90 transition"
                  title="点击查看大图"
                />
              ) : (
                <div className="w-20 h-20 bg-zinc-800 rounded flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="text-xs truncate" title={img.name}>{img.name}</div>
                <div className="text-[10px] opacity-55 mt-1 flex items-center gap-1.5">
                  <StatusPill
                    status={
                      skuCancelled && IN_FLIGHT.has(img.status)
                        ? "cancelled"
                        : img.status
                    }
                  />
                  {skuCancelled && IN_FLIGHT.has(img.status) && (
                    <span className="text-[9px] opacity-50">收尾中…</span>
                  )}
                </div>
                {img.err_msg && (
                  <div className="text-[10px] text-red-400 truncate mt-0.5" title={img.err_msg}>
                    {img.err_msg}
                  </div>
                )}
                {!skuCancelled && ["cutting", "generating", "composing"].includes(img.status) && (
                  <div className="h-1 bg-zinc-800 rounded mt-1.5 overflow-hidden">
                    <div
                      className="h-full bg-amber-500 transition-all"
                      style={{ width: `${img.progress}%` }}
                    />
                  </div>
                )}
              </div>
              <button
                onClick={() => onDelete(img.id, img.name)}
                className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-red-600 text-white text-[11px] leading-none opacity-0 group-hover:opacity-100 hover:bg-red-500"
                title="删除该原图"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </>
  );
}
