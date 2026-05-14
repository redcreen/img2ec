"use client";
/** SKU 详情页顶部控制 row：名字（点击改名）+ 状态 + 模板名 + 并发设置 +
 *  停止/下载/删除按钮 + SKU 目录 + 处理中实时进度行。
 *  从 page.tsx 抽出，便于试装和后续单测。 */
import { useState } from "react";
import { api } from "@/lib/api";
import type { SKU, Scene, SourceImage, Variant } from "@/lib/types";
import { PathBar } from "./PathBar";
import { StatusPill } from "./StatusPill";
import { ConcurrencyControl } from "./ConcurrencyControl";

const STAGE_LABEL: Record<string, string> = {
  ready: "待处理", pending: "排队中", cutting: "抠图中", generating: "Codex 生图中",
  composing: "派生平台尺寸", done: "图像完成", failed: "失败",
};

export function SkuHeader({
  sku, scene, skuPath, pid, sid,
  activeVariant, currentImg, currentImgIdx, totalImages,
  onCancel, onDelete, onAfterRename,
}: {
  sku: SKU;
  scene?: Scene;
  skuPath: string;
  pid: string;
  sid: string;
  activeVariant?: Variant;
  currentImg: SourceImage | null;
  currentImgIdx: number;
  totalImages: number;
  onCancel: () => void;
  onDelete: () => void;
  onAfterRename: () => Promise<void> | void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState("");

  const submitRename = async () => {
    const next = draft.trim();
    if (!next || next === sku.name) { setRenaming(false); return; }
    try {
      await api.patchSku(pid, sid, { name: next });
      await onAfterRename();
      setRenaming(false);
    } catch (err: any) {
      alert(err.message || "改名失败");
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
      <div className="flex items-center gap-3 mb-2 flex-wrap">
        {renaming ? (
          <form
            className="flex items-center gap-1.5"
            onSubmit={(e) => { e.preventDefault(); submitRename(); }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
              onKeyDown={(e) => { if (e.key === "Escape") setRenaming(false); }}
              className="px-2 py-0.5 text-base font-bold bg-zinc-950 border border-blue-500 rounded outline-none"
            />
            <button type="submit" className="text-[10px] px-2 py-1 bg-blue-600 rounded">保存</button>
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => setRenaming(false)}
              className="text-[10px] px-2 py-1 bg-zinc-700 rounded"
            >取消</button>
          </form>
        ) : (
          <strong
            className="text-base cursor-pointer hover:bg-zinc-800 px-1 rounded inline-flex items-center gap-1"
            title="点击改名"
            onClick={() => { setDraft(sku.name); setRenaming(true); }}
          >
            {sku.name}
            <span className="opacity-40 text-[10px]">✏️</span>
          </strong>
        )}
        <StatusPill status={sku.status} />
        {scene && (
          <span className="text-[11px] opacity-60">
            · 模板：<span className="text-zinc-200">{scene.name}</span>
          </span>
        )}
        <div className="flex-1" />
        <ConcurrencyControl />
        {sku.status === "running" && (
          <button
            onClick={onCancel}
            className="px-3 py-2 text-sm border border-amber-500 text-amber-300 rounded font-semibold hover:bg-amber-500/20"
          >⏹ 停止</button>
        )}
        {sku.status === "done" && (
          <a
            href={api.downloadSku(sku.id)}
            className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold"
          >⬇ 一键下载 zip</a>
        )}
        <button
          onClick={onDelete}
          className="text-red-400 border border-red-400 rounded px-2 py-1 text-xs"
        >删除</button>
      </div>
      <PathBar path={skuPath} label="SKU 目录" />
      {sku.status === "running" && currentImg && (
        <div className="mt-3 text-[11px] flex gap-2 flex-wrap">
          <span>
            处理 {activeVariant?.color_name} 第{" "}
            <strong>{currentImgIdx + 1}/{totalImages}</strong>:{" "}
            <span className="opacity-80">{currentImg.name}</span>
          </span>
          <span className="opacity-40">|</span>
          <span className="opacity-70">
            {STAGE_LABEL[currentImg.status] ?? currentImg.status} ({currentImg.progress}%)
          </span>
        </div>
      )}
    </div>
  );
}
