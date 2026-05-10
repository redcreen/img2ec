"use client";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { PathBar } from "@/components/PathBar";
import { StatusPill } from "@/components/StatusPill";
import { MasterGallery } from "@/components/MasterGallery";
import { DerivedTable } from "@/components/DerivedTable";

export default function SkuDetailPage() {
  const { pid, sid } = useParams<{ pid: string; sid: string }>();
  const router = useRouter();
  const { data: sku, mutate } = useSWR(
    sid ? `sku-${sid}` : null,
    () => api.getSku(pid, sid),
    { refreshInterval: 2000 } // 处理中每 2s 轮询；完成后停止
  );
  const { data: project } = useSWR(`project-${pid}`, () =>
    api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const { data: scenes } = useSWR(`scenes-${pid}`, () => api.listScenes(pid));

  if (!sku) return <p className="opacity-60">加载中…</p>;
  const scene = scenes?.find(s => s.id === sku.scene_id);
  const skuPath = project ? `${project.root_path}/${sku.name}` : "";

  const onProcess = async () => { await api.processSku(pid, sid); mutate(); };
  const onDelete = async () => {
    if (!confirm(`删除 SKU "${sku.name}"？`)) return;
    await api.deleteSku(pid, sid);
    router.push(`/projects/${pid}/skus`);
  };

  return (
    <div>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 mb-3">
        <div className="flex items-center gap-3 mb-2">
          <strong className="text-base">{sku.name}</strong>
          <StatusPill status={sku.status} />
          <div className="flex-1" />
          {sku.status === "ready" && <button onClick={onProcess} className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">▶ 开始处理</button>}
          {sku.status === "running" && <span className="text-sm opacity-60">⏳ 处理中…</span>}
          {sku.status === "done" && <a href={api.downloadSku(sku.id)} className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">⬇ 一键下载 zip</a>}
          {sku.status === "error" && <button onClick={onProcess} className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">▶ 重试失败项</button>}
          <button onClick={onDelete} className="text-red-400 border border-red-400 rounded px-2 py-1 text-xs">删除</button>
        </div>
        <PathBar path={skuPath} label="SKU 目录" />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <h3 className="text-xs uppercase opacity-50 mb-2">原图（{sku.images.length} 张）</h3>
          {sku.images.map(img => (
            <div key={img.id} className="bg-zinc-900 border border-zinc-700 rounded p-3 mb-2 flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-zinc-600 to-zinc-900 rounded flex items-center justify-center text-[10px] opacity-70">
                {img.name.slice(0, 4)}
              </div>
              <div className="flex-1">
                <div className="text-xs">{img.name}</div>
                <div className="text-[11px] opacity-55 mt-1 flex items-center gap-2">
                  <StatusPill status={img.status} />
                  {img.status === "done" && <span>· 输出 4 张</span>}
                  {img.err_msg && <span>· {img.err_msg}</span>}
                </div>
                {["cutting", "generating", "composing"].includes(img.status) && (
                  <div className="h-1 bg-zinc-800 rounded mt-1.5 overflow-hidden">
                    <div className="h-full bg-amber-500 transition-all" style={{ width: `${img.progress}%` }} />
                  </div>
                )}
              </div>
            </div>
          ))}
          {sku.status === "done" && (
            <div className="mt-6 space-y-4">
              <MasterGallery images={sku.images} />
              <DerivedTable images={sku.images} />
            </div>
          )}
        </div>

        <div>
          <div className="bg-zinc-900 border border-zinc-700 rounded p-3 mb-2 text-xs">
            <div className="opacity-50 uppercase mb-2">场景模板</div>
            {scene ? (
              <>
                <div className="font-semibold">{scene.name}</div>
                <div className="opacity-55 mt-1">{scene.category}</div>
                <div className="opacity-55 mt-2 line-clamp-3">{scene.prompt}</div>
              </>
            ) : <div>未设置</div>}
          </div>
          <div className="bg-zinc-900 border border-zinc-700 rounded p-3 text-xs">
            <div className="opacity-50 uppercase mb-2">输出平台</div>
            <div>✓ 抖店　✓ 视频号　✓ 淘宝　✓ 小红书</div>
            <div className="opacity-55 mt-2">MVP：每平台 1:1 主图 1 张</div>
          </div>
        </div>
      </div>
    </div>
  );
}
