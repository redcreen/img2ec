"use client";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { PathBar } from "@/components/PathBar";
import { StatusPill } from "@/components/StatusPill";
import { MasterGallery } from "@/components/MasterGallery";
import { DerivedTable } from "@/components/DerivedTable";
import { BizFieldsTabs } from "@/components/BizFieldsTabs";

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

  // 整体进度计算：每张原图 0-100%（cutting 0-10, generating 0-100, composing 0-10），
  // 5 master gen 在 generating 阶段做 5 步（每步 ~45s）。所有图 done 后还有 LLM + 详情页 ~10%。
  const STAGE_PROGRESS: Record<string, number> = {
    pending: 0, cutting: 5, generating: 10, composing: 90, done: 100, failed: 100,
  };
  const STAGE_LABEL: Record<string, string> = {
    pending: "排队中", cutting: "抠图中", generating: "AI 生背景中", composing: "派生平台尺寸",
    done: "图像完成", failed: "失败",
  };
  function imageOverallProgress(img: { status: string; progress: number }): number {
    const base = STAGE_PROGRESS[img.status] ?? 0;
    if (img.status === "generating") return base + (img.progress * 0.8);  // 10 → 90
    if (img.status === "cutting") return base + (img.progress * 0.05);    // 5 → 10
    if (img.status === "composing") return base + (img.progress * 0.1);   // 90 → 100
    return base;
  }
  const totalImages = sku.images.length;
  const avgImgProgress = totalImages
    ? sku.images.reduce((s, i) => s + imageOverallProgress(i), 0) / totalImages
    : 0;
  const allImagesDone = totalImages > 0 && sku.images.every(i => i.status === "done");
  // 所有图 done 但 SKU 还在 running → LLM + 详情页阶段（最后 10%）
  const overallPct = sku.status === "done" ? 100
    : allImagesDone && sku.status === "running" ? 92  // post-image stage
    : Math.min(89, avgImgProgress * 0.9);

  const currentImgIdx = sku.images.findIndex(i => i.status !== "done" && i.status !== "failed");
  const currentImg = currentImgIdx >= 0 ? sku.images[currentImgIdx] : null;
  // 预计输出 = 原图 × (5 master + 15 派生) + 3 详情页拼图
  const totalOutputs = totalImages * 20 + 3;

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

        {(sku.status === "running" || sku.status === "ready") && totalImages > 0 && (
          <div className="mt-3">
            <div className="flex items-center text-[11px] mb-1.5 gap-2 flex-wrap">
              <span className="font-semibold">{Math.round(overallPct)}%</span>
              <span className="opacity-40">|</span>
              <span>预计输出 <strong>{totalOutputs}</strong> 张图（含 5 master × {totalImages} + 15 派生 × {totalImages} + 3 详情页拼图）</span>
              {currentImg && (
                <>
                  <span className="opacity-40">|</span>
                  <span>正在处理第 <strong>{currentImgIdx + 1}/{totalImages}</strong> 张原图: <span className="opacity-80">{currentImg.name}</span></span>
                  <span className="opacity-40">|</span>
                  <span className="opacity-70">{STAGE_LABEL[currentImg.status] || currentImg.status} ({currentImg.progress}%)</span>
                </>
              )}
              {!currentImg && allImagesDone && sku.status === "running" && (
                <>
                  <span className="opacity-40">|</span>
                  <span className="opacity-70">所有图已生成 — 正在生成 3 平台文案 + 详情页拼图…</span>
                </>
              )}
            </div>
            <div className="h-2 bg-zinc-800 rounded overflow-hidden">
              <div className="h-full bg-blue-500 transition-all" style={{ width: `${overallPct}%` }} />
            </div>
          </div>
        )}
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
              <BizFieldsTabs skuId={sid} />
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
