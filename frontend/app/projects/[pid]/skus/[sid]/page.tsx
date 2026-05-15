"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { MasterGallery } from "@/components/MasterGallery";
import { PlatformTabs } from "@/components/PlatformTabs";
import { RatioSelector } from "@/components/RatioSelector";
import { PromptPreview } from "@/components/PromptPreview";
import { VariantTabs } from "@/components/VariantTabs";
import { Lightbox } from "@/components/Lightbox";
import { SceneSelectModal } from "@/components/SceneSelectModal";
import { SourceImageList } from "@/components/SourceImageList";
import { SkuHeader } from "@/components/SkuHeader";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { toProcessExtra, useGenConfig } from "@/lib/genConfig";
import { UndoProvider, useUndo } from "@/lib/useUndoableDelete";
import { useCuration } from "@/lib/curation";
import { useToast } from "@/lib/useToast";

export default function SkuDetailPage() {
  return (
    <ErrorBoundary>
      <UndoProvider>
        <SkuDetailPageInner />
      </UndoProvider>
    </ErrorBoundary>
  );
}

function SkuDetailPageInner() {
  const { pid, sid } = useParams<{ pid: string; sid: string }>();
  const router = useRouter();
  const undo = useUndo();
  const toast = useToast();
  const { data: sku, mutate } = useSWR(
    sid ? `sku-${sid}` : null,
    () => api.getSku(pid, sid),
    { refreshInterval: 2000 }
  );
  const { data: project } = useSWR(`project-${pid}`, () =>
    api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const { data: scenes } = useSWR(`scenes-${pid}`, () => api.listScenes(pid));
  const [sourceLightbox, setSourceLightbox] = useState<{ src: string; alt: string } | null>(null);
  const [activeVariantId, setActiveVariantId] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [genConfig, dispatchGen] = useGenConfig(sid);
  const [submitting, setSubmitting] = useState(false);  // 点击 → 后端 202 → 下次 poll 之间的盲窗
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  // 当 sku 加载后，默认激活第一个变体
  useEffect(() => {
    if (sku && sku.variants.length > 0 && !sku.variants.find(v => v.id === activeVariantId)) {
      setActiveVariantId(sku.variants[0].id);
    }
  }, [sku?.variants?.map(v => v.id).join("|")]);

  const cur = useCuration(sid, activeVariantId);

  if (!sku) return <p className="opacity-60">加载中…</p>;
  const scene = scenes?.find(s => s.id === sku.scene_id);
  const skuPath = project ? `${project.root_path}/${sku.name}` : "";
  const activeVariant = sku.variants.find(v => v.id === activeVariantId) ?? sku.variants[0];

  const onTriggerGen = async (args: {
    ratios: string[];
    dimStyles: string[];
    dimImageIndices: number[];
    dims: { length: number | null; width: number | null; height: number | null };
  }) => {
    if (!activeVariant || submitting) return;
    setSubmitting(true);
    try {
      const needSave = args.dimStyles.length > 0 && (
        args.dims.length !== sku.length_cm ||
        args.dims.width !== sku.width_cm ||
        args.dims.height !== sku.height_cm
      );
      if (needSave) {
        await api.updateDimensions(pid, sid, {
          length_cm: args.dims.length,
          width_cm: args.dims.width,
          height_cm: args.dims.height,
        });
      }
      const extra = toProcessExtra(genConfig);
      if (args.ratios.length > 0) {
        const imageIds = genConfig.selectedImgIds.size > 0
          ? Array.from(genConfig.selectedImgIds)
          : undefined;
        await api.processSku(pid, sid, args.ratios, activeVariant.id, extra, imageIds);
      }
      if (args.dimStyles.length > 0) {
        await api.regenerateDimension(pid, sid, args.dimStyles, activeVariant.id, args.dimImageIndices);
      }
      // 立刻刷一次，让 SWR 看到 status=running / dim=generating
      await mutate();
      // 给后端 ~3 秒兜底盲窗（mutate 已刷新，正常 isBusy 已 true，此处用 setTimeout 兜底防极端情况）
      setTimeout(() => setSubmitting(false), 3000);
    } catch (e: any) {
      toast.error("提交失败：" + e.message);
      setSubmitting(false);
    }
  };

  const onUploadToVariant = async (files: FileList | null) => {
    if (!files || files.length === 0 || !activeVariant) return;
    setUploading(true);
    try {
      for (const f of Array.from(files)) {
        await api.uploadImage(pid, sid, f, activeVariant.id);
      }
      mutate();
    } catch (e: any) {
      toast.error("上传失败：" + e.message);
    } finally {
      setUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  };

  const onReorderSourceImages = async (orderedIds: string[]) => {
    if (!activeVariant) return;
    const oldIds = activeVariant.images.map((im) => im.id);
    // idxMap[oldIdx] = newIdx
    const idxMap = oldIds.map((id) => orderedIds.indexOf(id));
    cur.remapImageIndices(idxMap);
    try {
      await api.reorderImages(pid, sid, activeVariant.id, orderedIds);
      await mutate();
    } catch (e: any) {
      toast.error("排序失败：" + e.message);
      await mutate();  // 回滚到服务端真实顺序
    }
  };
  const onDeleteImage = (iid: string, name: string) => {
    undo.enqueue({
      id: `img:${iid}`,
      label: `原图 ${name}`,
      doDelete: async () => {
        try {
          await api.deleteImage(pid, sid, iid);
          mutate();
        } catch (e: any) {
          toast.error("删除原图失败：" + e.message);
          mutate();
        }
      },
      onCancel: () => mutate(),
    });
  };
  const onCancel = async () => {
    if (!confirm("停止处理？已生成的图会保留，未生成的不再继续。")) return;
    try { await api.cancelSku(pid, sid); mutate(); }
    catch (e: any) { toast.error("停止失败：" + e.message); }
  };
  const onDelete = async () => {
    if (!confirm(`删除 SKU "${sku.name}"？`)) return;
    await api.deleteSku(pid, sid);
    router.push(`/projects/${pid}/skus`);
  };

  const STAGE_LABEL: Record<string, string> = {
    ready: "待处理", pending: "排队中", cutting: "抠图中", generating: "Codex 生图中", composing: "派生平台尺寸",
    done: "图像完成", failed: "失败",
  };

  // 当前变体的进度
  const variantImages = activeVariant?.images ?? [];
  const currentImgIdx = variantImages.findIndex(i => i.status !== "done" && i.status !== "failed");
  const currentImg = currentImgIdx >= 0 ? variantImages[currentImgIdx] : null;
  const totalImages = variantImages.length;
  const allImagesDone = totalImages > 0 && variantImages.every(i => i.status === "done");
  const hasAnyMaster = variantImages.some(i => i.master_urls && Object.keys(i.master_urls).length > 0);

  const existingRatios = Object.keys(variantImages[0]?.master_urls || {});

  // 给 RatioSelector 用的 live 状态徽章
  const dimStates: Record<string, { status: string }> = activeVariant?.dimension_states ?? {};
  const anyImgRunning = variantImages.some(i => ["pending", "cutting", "generating", "composing"].includes(i.status));
  const anyImgFailed = variantImages.some(i => i.status === "failed");
  const anyDimRunning = Object.values(dimStates).some(s => s.status === "generating");
  const dimRunningKeys = Object.entries(dimStates)
    .filter(([, s]) => s.status === "generating")
    .map(([k]) => k);
  const anyDimError = Object.values(dimStates).some(s => s.status === "error");
  // 本批待生成 = 所有 image pending_ratios 数总和（每个 ratio 算 1 张）
  const pendingTaskCount =
    variantImages.reduce((s, i) => s + (i.pending_ratios?.length || 0), 0)
    + dimRunningKeys.length;
  const isBusy = submitting || sku.status === "running" || anyImgRunning || anyDimRunning;
  const liveStatus: { running: boolean; text: string; tone: "running" | "done" | "failed" | "idle" } =
    submitting && !anyImgRunning && !anyDimRunning
      ? { running: true, tone: "running", text: "已提交 · 等待 worker…" }
      : isBusy
      ? {
          running: true,
          tone: "running",
          text: pendingTaskCount > 0
            ? `生成中 · 剩 ${pendingTaskCount} 张${currentImg && anyImgRunning ? ` · 当前 ${currentImg.name} · ${STAGE_LABEL[currentImg.status] || currentImg.status} ${currentImg.progress || 0}%` : ""}`
            : "处理中…",
        }
      : anyImgFailed || anyDimError
      ? { running: false, tone: "failed", text: anyDimError ? "尺寸图生成失败 — 可点击重生" : "上次有失败 — 可点击重生" }
      : allImagesDone
      ? { running: false, tone: "done", text: `已完成（${totalImages} 张原图）` }
      : { running: false, tone: "idle", text: "" };

  return (
    <div className="space-y-3">
      {/* 顶部 sticky 状态横幅：生成中独立展示，不挡按钮 */}
      {liveStatus.tone === "running" && (
        <div className="sticky top-0 z-30 -mx-3 px-4 py-2 bg-amber-900/85 backdrop-blur border-y border-amber-600/60 flex items-center gap-2 text-xs">
          <svg className="animate-spin h-3.5 w-3.5 text-amber-300" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
            <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" />
          </svg>
          <span className="text-amber-100 font-semibold">{liveStatus.text}</span>
          <span className="text-amber-200/70 text-[10px]">· 可继续点 ▶ 生成添加新任务（已在跑的图会跳过）</span>
        </div>
      )}
      <SkuHeader
        sku={sku} scene={scene} skuPath={skuPath}
        pid={pid} sid={sid}
        activeVariant={activeVariant}
        currentImg={currentImg}
        currentImgIdx={currentImgIdx}
        totalImages={totalImages}
        onCancel={onCancel}
        onDelete={onDelete}
        onAfterRename={async () => { await mutate(); }}
      />

      {/* 变体 tab */}
      <VariantTabs
        pid={pid}
        sid={sid}
        variants={sku.variants}
        activeId={activeVariant?.id ?? ""}
        onSelect={setActiveVariantId}
        onChanged={() => mutate()}
      />

      {/* 主体 2 列布局 */}
      {activeVariant && (
        <div className="grid grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)] gap-3">
          {/* 左列：原图 + 模板 + 生成规格 + 尺寸图（per variant） */}
          <div className="space-y-3">
            {/* 1. 原图 */}
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
              <div className="flex items-center mb-2 gap-2">
                <span className="text-xs uppercase opacity-50">
                  原图 · {activeVariant.color_name}（{variantImages.length}）
                </span>
                <div className="flex-1" />
                <button
                  onClick={() => uploadInputRef.current?.click()}
                  disabled={uploading}
                  className="text-[10px] bg-blue-600 hover:bg-blue-500 px-2 py-1 rounded font-semibold disabled:opacity-50"
                >{uploading ? "上传中…" : "+ 添加"}</button>
                <input
                  ref={uploadInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) => onUploadToVariant(e.target.files)}
                  className="hidden"
                />
              </div>
              <SourceImageList
                images={variantImages.filter((im) => !undo.isPending(`img:${im.id}`))}
                selected={genConfig.selectedImgIds}
                onToggleSelect={(id) => dispatchGen({ type: "toggle_img", id })}
                onSelectAll={() => dispatchGen({ type: "select_all", ids: variantImages.map(i => i.id) })}
                onClearSelection={() => dispatchGen({ type: "clear_selection" })}
                onDelete={onDeleteImage}
                onZoomSource={(img) => img.src_url && setSourceLightbox({ src: img.src_url, alt: img.name })}
                onReorder={onReorderSourceImages}
              />
            </div>

            {/* 2. 模板 + Prompt */}
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
              <PromptPreview
                pid={pid} sid={sid} scene={scene}
                extraPrompt={genConfig.extraPrompt}
                extraWeight={genConfig.extraWeight}
                extraNegativePrompt={genConfig.extraNegativePrompt}
                mode={genConfig.mode}
                onModeChange={(m) => dispatchGen({ type: "set_mode", value: m })}
                referenceImage={genConfig.referenceImage}
                onReferenceChange={(r) => dispatchGen({ type: "set_reference", value: r })}
                onExtraPromptChange={(v) => dispatchGen({ type: "set_prompt", value: v })}
                onExtraWeightChange={(v) => dispatchGen({ type: "set_weight", value: v })}
                onExtraNegativePromptChange={(v) => dispatchGen({ type: "set_negative", value: v })}
                onSceneChanged={() => mutate()}
              />
            </div>

            {/* 3. 生成规格（比例图 + 特写图 + 尺寸图） */}
            {variantImages.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
                <RatioSelector
                  existingRatios={Object.keys(variantImages[0]?.master_urls || {})}
                  existingDimStyles={
                    // 任一源图生成过 → 视为已生成（按 style 维度）
                    ["white", "template"].filter((s) =>
                      Object.keys(activeVariant.dimension_urls || {}).some(
                        (k) => k === s || k.startsWith(`${s}_img`)
                      )
                    )
                  }
                  initialDimensions={{
                    length_cm: sku.length_cm,
                    width_cm: sku.width_cm,
                    height_cm: sku.height_cm,
                  }}
                  sourceImages={variantImages.map((img) => ({
                    id: img.id,
                    name: img.name,
                    src_url: img.src_url,
                  }))}
                  busy={submitting}
                  liveStatus={liveStatus}
                  onTrigger={onTriggerGen}
                />
              </div>
            )}
          </div>

          {/* 右列：Master + 平台预览 */}
          <div className="space-y-3 min-w-0">
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
              <MasterGallery
                images={variantImages}
                variant={activeVariant}
                pid={pid}
                sid={sid}
                onChanged={() => mutate()}
              />
            </div>

            <PlatformTabs pid={pid} skuId={sid} variant={activeVariant} sku={sku} activeVariantId={activeVariant.id} onSelectVariant={setActiveVariantId} onChanged={() => mutate()} />
          </div>
        </div>
      )}

      {/* 底部下载 */}
      {sku.status === "done" && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 flex items-center gap-3">
          <div className="flex-1">
            <div className="text-sm font-semibold">预览满意？打包下载全部图片</div>
            <div className="text-[11px] opacity-60 mt-0.5">
              包含所有变体的 Master + 派生 + 尺寸图 + 详情页拼图
            </div>
          </div>
          <a
            href={api.downloadSku(sku.id)}
            className="px-4 py-2 text-sm bg-emerald-600 hover:bg-emerald-500 rounded font-bold"
          >
            ⬇ 下载 zip
          </a>
        </div>
      )}

      {sourceLightbox && (
        <Lightbox
          src={sourceLightbox.src}
          alt={sourceLightbox.alt}
          onClose={() => setSourceLightbox(null)}
        />
      )}
    </div>
  );
}
