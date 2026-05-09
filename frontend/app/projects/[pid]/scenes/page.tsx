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

  return (
    <>
      <div className="flex justify-end mb-3">
        <button onClick={() => setCreating(true)}
          className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">+ 新建场景</button>
      </div>
      {scenes && scenes.length === 0 && <p className="opacity-60 text-center py-12">还没场景，点右上新建</p>}
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
