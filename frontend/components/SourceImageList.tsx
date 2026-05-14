"use client";
import type { SourceImage } from "@/lib/types";
import { StatusPill } from "./StatusPill";

/** 原图卡列表，含 checkbox 多选、状态、进度条、删除。 */
export function SourceImageList({
  images, selected, onToggleSelect, onSelectAll, onClearSelection,
  onDelete, onZoomSource,
}: {
  images: SourceImage[];
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onDelete: (iid: string, name: string) => void;
  onZoomSource: (img: SourceImage) => void;
}) {
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
      </div>
      <div className="space-y-2 max-h-[480px] overflow-y-auto">
        {images.map((img) => {
          const isSelected = selected.has(img.id);
          return (
            <div
              key={img.id}
              className={`group bg-zinc-950 border rounded p-2 flex items-center gap-3 relative ${
                isSelected ? "border-blue-500" : "border-zinc-800"
              }`}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleSelect(img.id)}
                className="w-4 h-4 accent-blue-500 cursor-pointer flex-shrink-0"
                title="勾选后只生成选中的"
              />
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
                  <StatusPill status={img.status} />
                </div>
                {img.err_msg && (
                  <div className="text-[10px] text-red-400 truncate mt-0.5" title={img.err_msg}>
                    {img.err_msg}
                  </div>
                )}
                {["cutting", "generating", "composing"].includes(img.status) && (
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
