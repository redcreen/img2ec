"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { SceneCard } from "@/components/SceneCard";
import { SceneEditorModal } from "@/components/SceneEditorModal";
import type { Scene } from "@/lib/types";

export default function ScenesPage() {
  const { pid } = useParams<{ pid: string }>();
  const { data: scenes, mutate } = useSWR(pid ? `scenes-${pid}` : null, () => api.listScenes(pid));
  const [editing, setEditing] = useState<Scene | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);

  const onImport = async () => {
    setImporting(true);
    try {
      await api.importDefaultScenes(pid);
      await mutate();
    } catch (e: any) {
      alert("导入失败：" + e.message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <>
      <div className="flex justify-end gap-2 mb-3">
        <button
          onClick={onImport}
          disabled={importing}
          className="px-3 py-2 text-sm border border-zinc-700 rounded hover:border-blue-500 disabled:opacity-50"
        >{importing ? "导入中…" : "导入默认 16 场景"}</button>
        <button onClick={() => setCreating(true)}
          className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">+ 新建场景</button>
      </div>
      {scenes && scenes.length === 0 && (
        <div className="opacity-60 text-center py-12">
          <p className="text-sm">还没场景。点右上「导入默认 16 场景」一键加齐内置库（推荐），</p>
          <p className="text-xs mt-1">或「新建场景」自己写一个。</p>
        </div>
      )}
      <div className="grid grid-cols-4 gap-3">
        {scenes?.map(sc => <SceneCard key={sc.id} scene={sc} onClick={() => setEditing(sc)} />)}
      </div>
      {(editing || creating) && (
        <SceneEditorModal pid={pid} scene={editing}
          onClose={() => { setEditing(null); setCreating(false); }}
          onSaved={() => { setEditing(null); setCreating(false); mutate(); }} />
      )}
    </>
  );
}
