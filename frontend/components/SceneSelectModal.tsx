"use client";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { FESTIVALS, type Scene } from "@/lib/types";

/** 给单张原图选模板（per-image scene override）。点 "用默认" = scene_id=null。 */
export function SceneSelectModal({
  pid, currentSceneId, imageName, onPick, onClose,
}: {
  pid: string;
  currentSceneId?: string | null;
  imageName: string;
  onPick: (sceneId: string | null) => Promise<void> | void;
  onClose: () => void;
}) {
  const { data: scenes } = useSWR(`scenes-${pid}`, () => api.listScenes(pid));
  const [filter, setFilter] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const list = useMemo(() => {
    if (!scenes) return [];
    return scenes.filter((s: Scene) => !filter || (s.festival || "通用") === filter);
  }, [scenes, filter]);

  const pick = async (sceneId: string | null) => {
    if (busy) return;
    setBusy(true);
    try {
      await onPick(sceneId);
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div onClick={onClose} className="fixed inset-0 bg-black/65 z-50 flex items-center justify-center p-4">
      <div onClick={(e) => e.stopPropagation()}
        className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 w-[760px] max-h-[80vh] flex flex-col">
        <div className="flex items-center mb-3">
          <h3 className="text-sm font-semibold">为「{imageName}」选模板</h3>
          <div className="flex-1" />
          <button onClick={onClose} className="opacity-60 hover:opacity-100">✕</button>
        </div>

        <div className="flex gap-1 mb-3 flex-wrap items-center">
          <button onClick={() => pick(null)} disabled={busy}
            className={`text-[11px] px-2.5 py-1 rounded border ${
              currentSceneId === null || currentSceneId === undefined
                ? "bg-emerald-700 text-white border-emerald-600"
                : "bg-zinc-800 border-zinc-700 hover:border-emerald-500"
            } disabled:opacity-40`}
            title="清除 per-image 模板，回退到 SKU 默认模板"
          >🌟 用 SKU 默认模板</button>
          <span className="text-[10px] opacity-50 mx-2">·</span>
          <span className="text-[10px] opacity-60">节庆:</span>
          <Chip label="全部" active={!filter} onClick={() => setFilter("")} />
          {FESTIVALS.map((f) => (
            <Chip key={f} label={f} active={filter === f} onClick={() => setFilter(f)} />
          ))}
        </div>

        <div className="grid grid-cols-4 gap-2 overflow-y-auto pr-1">
          {list.map((sc) => {
            const active = sc.id === currentSceneId;
            return (
              <button
                key={sc.id}
                onClick={() => pick(sc.id)}
                disabled={busy}
                className={`text-left p-1.5 rounded border-2 transition ${
                  active
                    ? "border-blue-500 bg-zinc-800"
                    : "border-zinc-700 bg-zinc-950 hover:border-zinc-500"
                } disabled:opacity-40`}
              >
                <div className="aspect-[4/3] rounded overflow-hidden bg-zinc-800 mb-1 relative">
                  {sc.cover_url ? (
                    <img src={sc.cover_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[10px] opacity-40">无图</div>
                  )}
                  <span className="absolute top-1 left-1 text-[9px] bg-black/65 text-white px-1 rounded">
                    {sc.festival || "通用"}
                  </span>
                </div>
                <div className="text-[11px] font-semibold truncate" title={sc.name}>{sc.name}</div>
                <div className="text-[9px] opacity-55 line-clamp-2">{sc.desc || sc.category}</div>
              </button>
            );
          })}
          {list.length === 0 && (
            <p className="col-span-4 text-center text-xs opacity-50 py-12">没有可选模板。先去场景库添加。</p>
          )}
        </div>
      </div>
    </div>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`text-[10px] px-2 py-0.5 rounded border ${
        active ? "bg-blue-600 text-white border-blue-500"
               : "bg-zinc-950 text-zinc-300 border-zinc-700 hover:border-zinc-500"
      }`}
    >{label}</button>
  );
}
