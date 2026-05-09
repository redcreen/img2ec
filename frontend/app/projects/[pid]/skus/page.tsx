"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { PathBar } from "@/components/PathBar";
import { SkuRow } from "@/components/SkuRow";
import { NewSkuModal } from "@/components/NewSkuModal";

export default function SkusPage() {
  const { pid } = useParams<{ pid: string }>();
  const router = useRouter();
  const { data: project } = useSWR(`project-${pid}`, () =>
    api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const { data: skus, mutate } = useSWR(`skus-${pid}`, () => api.listSkus(pid));
  const { data: scenes } = useSWR(`scenes-${pid}`, () => api.listScenes(pid));
  const [showNew, setShowNew] = useState(false);

  const sceneNameById = (id: string | null) =>
    scenes?.find(s => s.id === id)?.name ?? "未选";

  return (
    <>
      {project && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 mb-3 flex justify-between items-center gap-3">
          <PathBar path={project.root_path} label="项目目录（本地）" />
          <button onClick={() => setShowNew(true)}
            className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold whitespace-nowrap">+ 新建 SKU</button>
        </div>
      )}
      {skus && skus.length === 0 && <p className="text-center opacity-60 py-12">还没 SKU</p>}
      {skus?.map(s => <SkuRow key={s.id} sku={s} sceneName={sceneNameById(s.scene_id)} />)}
      {showNew && project && scenes && (
        <NewSkuModal pid={pid} scenes={scenes}
          onClose={() => setShowNew(false)}
          onCreated={async (sid) => {
            await api.processSku(pid, sid);
            mutate();
            router.push(`/projects/${pid}/skus/${sid}`);
          }} />
      )}
    </>
  );
}
