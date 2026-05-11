"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { PathBar } from "@/components/PathBar";
import { StatusPill } from "@/components/StatusPill";
import { MasterGallery } from "@/components/MasterGallery";
import { PlatformTabs } from "@/components/PlatformTabs";
import { RatioSelector } from "@/components/RatioSelector";
import { PromptPreview } from "@/components/PromptPreview";
import { VariantTabs } from "@/components/VariantTabs";
import { Lightbox } from "@/components/Lightbox";

export default function SkuDetailPage() {
  const { pid, sid } = useParams<{ pid: string; sid: string }>();
  const router = useRouter();
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
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  // 当 sku 加载后，默认激活第一个变体
  useEffect(() => {
    if (sku && sku.variants.length > 0 && !sku.variants.find(v => v.id === activeVariantId)) {
      setActiveVariantId(sku.variants[0].id);
    }
  }, [sku?.variants?.map(v => v.id).join("|")]);

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
    if (!activeVariant) return;
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
      if (args.ratios.length > 0) {
        await api.processSku(pid, sid, args.ratios, activeVariant.id);
      }
      if (args.dimStyles.length > 0) {
        await api.regenerateDimension(pid, sid, args.dimStyles, activeVariant.id, args.dimImageIndices);
      }
      mutate();
    } catch (e: any) {
      alert("提交失败：" + e.message);
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
      alert("上传失败：" + e.message);
    } finally {
      setUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  };

  const onDeleteImage = async (iid: string, name: string) => {
    if (!confirm(`删除原图「${name}」？该原图对应的生成图也会失效（文件保留在磁盘）。`)) return;
    try {
      await api.deleteImage(pid, sid, iid);
      mutate();
    } catch (e: any) {
      alert("删除失败：" + e.message);
    }
  };
  const onCancel = async () => {
    if (!confirm("停止处理？已生成的图会保留，未生成的不再继续。")) return;
    try { await api.cancelSku(pid, sid); mutate(); }
    catch (e: any) { alert("停止失败：" + e.message); }
  };
  const onDelete = async () => {
    if (!confirm(`删除 SKU "${sku.name}"？`)) return;
    await api.deleteSku(pid, sid);
    router.push(`/projects/${pid}/skus`);
  };

  const STAGE_LABEL: Record<string, string> = {
    pending: "排队中", cutting: "抠图中", generating: "Codex 生图中", composing: "派生平台尺寸",
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

  return (
    <div className="space-y-3">
      {/* Top header */}
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <strong className="text-base">{sku.name}</strong>
          <StatusPill status={sku.status} />
          {scene && (
            <span className="text-[11px] opacity-60">
              · 模板：<span className="text-zinc-200">{scene.name}</span>
            </span>
          )}
          <div className="flex-1" />
          {sku.status === "running" && (
            <button onClick={onCancel}
              className="px-3 py-2 text-sm border border-amber-500 text-amber-300 rounded font-semibold hover:bg-amber-500/20">
              ⏹ 停止
            </button>
          )}
          {sku.status === "done" && (
            <a href={api.downloadSku(sku.id)}
              className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">
              ⬇ 一键下载 zip
            </a>
          )}
          <button onClick={onDelete}
            className="text-red-400 border border-red-400 rounded px-2 py-1 text-xs">删除</button>
        </div>
        <PathBar path={skuPath} label="SKU 目录" />
        {sku.status === "running" && currentImg && (
          <div className="mt-3 text-[11px] flex gap-2 flex-wrap">
            <span>处理 {activeVariant?.color_name} 第 <strong>{currentImgIdx + 1}/{totalImages}</strong>: <span className="opacity-80">{currentImg.name}</span></span>
            <span className="opacity-40">|</span>
            <span className="opacity-70">{STAGE_LABEL[currentImg.status]} ({currentImg.progress}%)</span>
          </div>
        )}
      </div>

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
              {variantImages.length === 0 ? (
                <p className="text-xs opacity-60">该变体还没上传原图 — 点右上"+ 添加"</p>
              ) : (
                <div className="space-y-2 max-h-[480px] overflow-y-auto">
                  {variantImages.map(img => (
                    <div key={img.id}
                      className="group bg-zinc-950 border border-zinc-800 rounded p-2 flex items-center gap-3 relative">
                      {img.src_url ? (
                        <img src={img.src_url} alt={img.name}
                          onClick={() => setSourceLightbox({ src: img.src_url!, alt: img.name })}
                          className="w-20 h-20 object-cover rounded flex-shrink-0 cursor-zoom-in hover:opacity-90 transition"
                          title="点击查看大图" />
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
                            <div className="h-full bg-amber-500 transition-all"
                              style={{ width: `${img.progress}%` }} />
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => onDeleteImage(img.id, img.name)}
                        className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-red-600 text-white text-[11px] leading-none opacity-0 group-hover:opacity-100 hover:bg-red-500"
                        title="删除该原图"
                      >×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 2. 模板 + Prompt */}
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
              <PromptPreview pid={pid} sid={sid} scene={scene} />
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
                  busy={false}
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
