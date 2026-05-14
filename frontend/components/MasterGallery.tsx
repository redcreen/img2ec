"use client";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useCuration, type ImageKey } from "@/lib/curation";
import type { SourceImage, Variant } from "@/lib/types";
import { useUndo } from "@/lib/useUndoableDelete";
import { Lightbox } from "./Lightbox";
import { RatedImage } from "./RatedImage";

interface MasterVersion { path: string; url: string; }

const RATIO_KEYS = ["1x1", "long", "3x4", "9x16", "16x9"] as const;
const CLOSEUP_KEYS = ["front", "side", "detail"] as const;
const RATIO_LABEL: Record<string, string> = {
  "1x1": "1:1", "long": "750w", "3x4": "3:4", "9x16": "9:16", "16x9": "16:9",
  "front": "正面", "side": "侧面", "detail": "细节",
};
const SHARED_BY: Record<string, string> = {
  "1x1":  "抖店/视频号/淘宝/小红书主图",
  "long": "4 平台详情页",
  "3x4":  "抖店/小红书封面",
  "9x16": "抖店视频封面",
  "16x9": "淘宝视频封面",
  "front":  "特写图（正面）",
  "side":   "特写图（侧面）",
  "detail": "特写图（细节）",
};
const RATIO_ORDER = ["1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"];

type ActiveTab =
  | { kind: "image"; idx: number }
  | { kind: "dim" }
  | { kind: "library" };

interface DimEntry { key: string; style: string; imgIdx: number; url: string; }
interface LibOpt { key: ImageKey; url: string; label: string; }

export function MasterGallery({
  images, variant, pid, sid, onChanged,
}: {
  images: SourceImage[];
  variant: Variant;
  pid: string;
  sid: string;
  onChanged: () => void;
}) {
  const cur = useCuration(sid, variant.id);
  const undo = useUndo();
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null);
  const [active, setActive] = useState<ActiveTab>({ kind: "image", idx: 0 });
  const [thumbBusy, setThumbBusy] = useState(false);
  const [tabBusy, setTabBusy] = useState(false);
  const [deletingPath, setDeletingPath] = useState<string | null>(null);

  useEffect(() => { setActive({ kind: "image", idx: 0 }); }, [variant.id, images.length]);

  // dim entries
  const dimEntries: DimEntry[] = [];
  for (const [k, url] of Object.entries(variant.dimension_urls || {})) {
    const m = k.match(/^(white|template)_img(\d+)$/);
    if (m) dimEntries.push({ key: k, style: m[1], imgIdx: parseInt(m[2]), url });
  }
  dimEntries.sort((a, b) =>
    a.style === b.style ? a.imgIdx - b.imgIdx : a.style.localeCompare(b.style)
  );

  // SKU 选图候选 keys（用 url 文件名匹配）
  const availableMap = useMemo(() => {
    const map = new Map<ImageKey, LibOpt>();
    images.forEach((img, idx) => {
      for (const [ratio, url] of Object.entries(img.master_urls || {})) {
        if (!url) continue;
        const k: ImageKey = `img${idx}:${ratio}`;
        map.set(k, { key: k, url, label: `${RATIO_LABEL[ratio] || ratio} · 原图${idx + 1}` });
      }
    });
    for (const d of dimEntries) {
      const key: ImageKey = `size_${d.key}`;
      map.set(key, {
        key,
        url: d.url,
        label: `${d.style === "white" ? "尺寸图·白底" : "尺寸图·模板"} · 原图${d.imgIdx + 1}`,
      });
    }
    return map;
  }, [images, variant.dimension_urls, dimEntries.length]);

  const libraryKeys = useMemo(() => {
    const ks = Array.from(availableMap.keys());
    return ks.sort((a, b) => {
      const ai = a.startsWith("size_") ? 9999 : parseInt(a.slice(3, a.indexOf(":")));
      const bi = b.startsWith("size_") ? 9999 : parseInt(b.slice(3, b.indexOf(":")));
      if (ai !== bi) return ai - bi;
      const ar = a.startsWith("size_") ? a : a.split(":")[1];
      const br = b.startsWith("size_") ? b : b.split(":")[1];
      const aIdx = RATIO_ORDER.indexOf(ar);
      const bIdx = RATIO_ORDER.indexOf(br);
      return (aIdx < 0 ? 999 : aIdx) - (bIdx < 0 ? 999 : bIdx);
    });
  }, [availableMap]);

  const thumbKeys = useMemo<ImageKey[]>(() => {
    if (!variant.sku_thumb_paths?.length) return [];
    return variant.sku_thumb_paths.map((p) => {
      const tail = p.split("/").pop()!;
      for (const [k, opt] of availableMap.entries()) {
        if (decodeURIComponent(opt.url.split("/").pop()?.split("?")[0] || "") === tail) return k;
      }
      return "";
    }).filter(Boolean) as ImageKey[];
  }, [variant.sku_thumb_paths, availableMap]);

  const setThumbs = async (keys: ImageKey[]) => {
    setThumbBusy(true);
    try {
      await api.setVariantThumbnails(pid, sid, variant.id, keys);
      onChanged();
    } catch (e: any) {
      alert("更新 SKU 选图失败：" + e.message);
    } finally {
      setThumbBusy(false);
    }
  };
  const toggleThumb = (k: ImageKey) =>
    setThumbs(thumbKeys.includes(k) ? thumbKeys.filter((x) => x !== k) : [...thumbKeys, k]);

  const totalGenerated =
    images.reduce((s, i) => s + Object.keys(i.master_urls || {}).length, 0) +
    dimEntries.length;

  if (images.length === 0) {
    return (
      <div>
        <div className="text-xs uppercase opacity-50 mb-2">Master 资产</div>
        <p className="text-xs opacity-60">该变体还没上传原图</p>
      </div>
    );
  }

  const onDeleteAllForImage = (img: SourceImage) => {
    undo.enqueue({
      id: `bulk-master:${img.id}`,
      label: `「${img.name}」全部 master`,
      doDelete: async () => {
        try {
          await api.deleteAllMastersForImage(pid, sid, img.id);
          onChanged();
        } catch (e: any) {
          alert("批删失败：" + e.message);
          onChanged();
        }
      },
      onCancel: () => onChanged(),
    });
  };
  const onRegenImage = async (img: SourceImage) => {
    if (tabBusy) return;
    const existing = Object.keys(img.master_urls || {});
    const ratios = existing.length > 0 ? existing : ["1x1", "long", "3x4", "9x16", "16x9"];
    setTabBusy(true);
    try {
      await api.regenerateImage(pid, sid, img.id, { ratios });
      onChanged();
    } catch (e: any) { alert("提交失败：" + e.message); }
    finally { setTabBusy(false); }
  };

  // 单格重生：纯入队，不再检查 in-flight；后端通过 celery 队列调度
  const onRegenSingle = async (img: SourceImage, ratio: string) => {
    if (tabBusy) return;
    setTabBusy(true);
    try {
      await api.regenerateImage(pid, sid, img.id, { ratios: [ratio] });
      onChanged();
    } catch (e: any) { alert("提交失败：" + e.message); }
    finally { setTabBusy(false); }
  };
  const onDeleteAllDim = () => {
    undo.enqueue({
      id: `bulk-dim:${variant.id}`,
      label: `「${variant.color_name}」全部尺寸图`,
      doDelete: async () => {
        try {
          await api.deleteAllDimension(pid, sid, variant.id);
          onChanged();
        } catch (e: any) {
          alert("批删失败：" + e.message);
          onChanged();
        }
      },
      onCancel: () => onChanged(),
    });
  };
  const onRegenAllDim = async () => {
    if (tabBusy) return;
    if (!variant.images.length) { alert("没有原图"); return; }
    // 仅重生**已存在**的 (style, img_idx) 组合
    const combos: Array<{ style: string; idx: number }> = [];
    for (const k of Object.keys(variant.dimension_urls || {})) {
      const m = k.match(/^(white|template)_img(\d+)$/);
      if (m) combos.push({ style: m[1], idx: parseInt(m[2]) });
    }
    if (combos.length === 0) {
      alert("当前还没生成过任何尺寸图。请到上方「生成规格」勾选尺寸图风格再生成。");
      return;
    }
    setTabBusy(true);
    try {
      // 按 style 分组，每个 style 跑自己实际有的 indices
      const byStyle: Record<string, number[]> = {};
      for (const { style, idx } of combos) {
        (byStyle[style] = byStyle[style] || []).push(idx);
      }
      for (const [style, indices] of Object.entries(byStyle)) {
        await api.regenerateDimension(pid, sid, [style], variant.id, indices.sort());
      }
      onChanged();
    } catch (e: any) { alert("提交失败：" + e.message); }
    finally { setTabBusy(false); }
  };

  // 删除走 undo 队列：点 × 立即从 UI 隐藏（isPending 过滤），10s 内可撤销；
  // 超时 doDelete 触发真删。同 path 二次入队 → 重置倒计时。
  const deleteVersion = (imageId: string, ratio: string, path: string, imgName: string) => {
    const label = `${imgName} · ${ratio}`;
    undo.enqueue({
      id: path,
      label,
      doDelete: async () => {
        try {
          await api.deleteMasterVersion(pid, sid, { image_id: imageId, ratio, path });
          onChanged();
        } catch (e: any) {
          alert("删除失败：" + e.message);
          onChanged();
        }
      },
      onCancel: () => onChanged(),  // 让 SWR 重渲，撤销后立刻可见
    });
  };
  const deleteDim = (style: string, imageIdx: number) => {
    const id = `dim:${variant.id}:${style}_img${imageIdx}`;
    const label = `尺寸图${style === "white" ? "·白底" : "·模板"} · 原图${imageIdx + 1}`;
    undo.enqueue({
      id, label,
      doDelete: async () => {
        try {
          await api.deleteDimensionImage(pid, sid, { variant_id: variant.id, style, image_idx: imageIdx });
          onChanged();
        } catch (e: any) {
          alert("删除失败：" + e.message);
          onChanged();
        }
      },
      onCancel: () => onChanged(),
    });
  };

  const cellProps = (
    k: ImageKey, url: string | undefined, label: string, sub?: string, accent?: boolean,
    versions?: MasterVersion[],
    onDeleteVersion?: (path: string) => void,
    imgStatus?: string,
    onRegenEmpty?: () => void,
    isPending?: boolean,
  ) => ({
    imageKey: k, url, label, sub, accent,
    cur, isThumb: thumbKeys.includes(k), thumbBusy,
    onToggleThumb: () => toggleThumb(k),
    onZoom: (u: string, alt: string) => setLightbox({ src: u, alt }),
    versions, onDeleteVersion, deletingPath, imgStatus, onRegenEmpty, isPending,
  });

  return (
    <div>
      <div className="text-xs uppercase opacity-50 mb-2">
        Master 资产（已生成 {totalGenerated} 张 · 每张图可加入 主图/详情图/SKU 选图）
      </div>

      {/* tab strip */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3">
        {images.map((img, i) => {
          const isActive = active.kind === "image" && active.idx === i;
          return (
            <button
              key={img.id}
              onClick={() => setActive({ kind: "image", idx: i })}
              className={`flex-shrink-0 flex items-center gap-2 px-2 py-1.5 rounded border-2 transition ${
                isActive ? "border-blue-500 bg-zinc-800"
                         : "border-zinc-700 hover:border-zinc-500 opacity-75 hover:opacity-100"
              }`}
              title={img.name}
            >
              {img.src_url ? (
                <img src={img.src_url} alt="" className="w-8 h-8 object-cover rounded" />
              ) : (
                <div className="w-8 h-8 bg-zinc-800 rounded" />
              )}
              <span className="text-[11px] max-w-[120px] truncate">原图 {i + 1}</span>
              <span className="text-[10px] opacity-50">
                {Object.keys(img.master_urls || {}).length}/8
              </span>
            </button>
          );
        })}
        {dimEntries.length > 0 && (
          <button
            onClick={() => setActive({ kind: "dim" })}
            className={`flex-shrink-0 flex items-center gap-2 px-2 py-1.5 rounded border-2 transition ${
              active.kind === "dim" ? "border-indigo-500 bg-zinc-800"
                                    : "border-indigo-800 hover:border-indigo-500 opacity-75 hover:opacity-100"
            }`}
            title="尺寸图（全部）"
          >
            <img src={dimEntries[0].url} alt="" className="w-8 h-8 object-cover rounded bg-white" />
            <span className="text-[11px]">尺寸图</span>
            <span className="text-[10px] opacity-60">{dimEntries.length}</span>
          </button>
        )}
        <button
          onClick={() => setActive({ kind: "library" })}
          className={`flex-shrink-0 flex items-center gap-2 px-2 py-1.5 rounded border-2 transition ${
            active.kind === "library" ? "border-emerald-500 bg-zinc-800"
                                      : "border-emerald-800 hover:border-emerald-500 opacity-75 hover:opacity-100"
          }`}
          title="图片库（全部）"
        >
          <div className="w-8 h-8 grid grid-cols-2 gap-px bg-zinc-700 rounded overflow-hidden">
            {libraryKeys.slice(0, 4).map((k) => {
              const o = availableMap.get(k)!;
              return <img key={k} src={o.url} alt="" className="w-full h-full object-cover" />;
            })}
          </div>
          <span className="text-[11px]">图片库</span>
          <span className="text-[10px] opacity-60">{libraryKeys.length}</span>
        </button>
      </div>

      {/* content */}
      {active.kind === "image" && (() => {
        const idx = Math.min(active.idx, images.length - 1);
        const img = images[idx];
        // 批量删除该原图所有 master 排队中 → 全网格视作空（10s 内可撤销）
        if (undo.isPending(`bulk-master:${img.id}`)) {
          return (
            <div className="text-xs opacity-60 py-6 text-center">
              正在删除「{img.name}」全部 master（右下角可撤销）…
            </div>
          );
        }
        const hasCloseup = CLOSEUP_KEYS.some((k) => img.master_urls?.[k]);
        return (
          <>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <div className="text-[11px] opacity-60">{img.name}</div>
              <div className="flex-1" />
              <button
                onClick={() => onRegenImage(img)}
                disabled={tabBusy}
                className="text-[10px] px-2 py-1 rounded bg-blue-600/80 hover:bg-blue-500 disabled:opacity-40"
                title={`重新生成该原图的全部 8 个规格（保留历史）`}
              >▶ 重新生成全部</button>
              <button
                onClick={() => onDeleteAllForImage(img)}
                disabled={tabBusy}
                className="text-[10px] px-2 py-1 rounded bg-red-700/60 hover:bg-red-600 disabled:opacity-40"
                title="删除该原图下所有 master + 历史 + 派生"
              >🗑 全部删除</button>
            </div>
            <div className="text-[10px] opacity-40 mb-1">比例图 <span className="opacity-60">（重新生成保留历史；× 删除版本）</span></div>
            <div className="grid grid-cols-5 gap-1.5 mb-3">
              {RATIO_KEYS.map((r) => {
                const allVersions = (img.master_history_urls?.[r] || []) as MasterVersion[];
                const versions = allVersions.filter(v => !undo.isPending(v.path));
                const pending = (img.pending_ratios || []).includes(r);
                // 主图 url：若头版本(versions[0])被 pending，整张 cell 视为已删
                const headPath = (img.master_paths || {})[r];
                const cellUrl = (headPath && undo.isPending(headPath)) ? undefined
                  : (versions.length === 0 && allVersions.length > 0 ? undefined : img.master_urls?.[r]);
                return (
                  <CurationCell
                    key={r}
                    {...cellProps(
                      `img${idx}:${r}` as ImageKey, cellUrl, RATIO_LABEL[r] || r, SHARED_BY[r],
                      false, versions, (p) => deleteVersion(img.id, r, p, img.name), img.status,
                      () => onRegenSingle(img, r), pending,
                    )}
                  />
                );
              })}
            </div>
            {hasCloseup && (
              <>
                <div className="text-[10px] opacity-40 mb-1">特写图（白底）</div>
                <div className="grid grid-cols-5 gap-1.5">
                  {CLOSEUP_KEYS.filter((k) => img.master_urls?.[k]).map((r) => {
                    const allVersions = (img.master_history_urls?.[r] || []) as MasterVersion[];
                    const versions = allVersions.filter(v => !undo.isPending(v.path));
                    const pending = (img.pending_ratios || []).includes(r);
                    const headPath = (img.master_paths || {})[r];
                    const cellUrl = (headPath && undo.isPending(headPath)) ? undefined
                      : (versions.length === 0 && allVersions.length > 0 ? undefined : img.master_urls?.[r]);
                    return (
                      <CurationCell
                        key={r}
                        {...cellProps(
                          `img${idx}:${r}` as ImageKey, cellUrl, RATIO_LABEL[r] || r, SHARED_BY[r],
                          false, versions, (p) => deleteVersion(img.id, r, p, img.name), img.status,
                          () => onRegenSingle(img, r), pending,
                        )}
                      />
                    );
                  })}
                </div>
              </>
            )}
          </>
        );
      })()}

      {active.kind === "dim" && undo.isPending(`bulk-dim:${variant.id}`) && (
        <div className="text-xs opacity-60 py-6 text-center">
          正在删除「{variant.color_name}」全部尺寸图（右下角可撤销）…
        </div>
      )}
      {active.kind === "dim" && !undo.isPending(`bulk-dim:${variant.id}`) && (
        <div>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <div className="text-[11px] opacity-60">所有尺寸图（{dimEntries.length}）</div>
            <div className="flex-1" />
            <button
              onClick={onRegenAllDim}
              disabled={tabBusy}
              className="text-[10px] px-2 py-1 rounded bg-blue-600/80 hover:bg-blue-500 disabled:opacity-40"
              title="重生该变体所有原图的全部 style 尺寸图"
            >▶ 重新生成全部</button>
            <button
              onClick={onDeleteAllDim}
              disabled={tabBusy}
              className="text-[10px] px-2 py-1 rounded bg-red-700/60 hover:bg-red-600 disabled:opacity-40"
              title="删除所有尺寸图（不可撤销）"
            >🗑 全部删除</button>
          </div>
          <div className="text-[10px] opacity-40 mb-1">× 单张删除</div>
          <div className="grid grid-cols-5 gap-1.5">
            {dimEntries
              .filter((d) => !undo.isPending(`dim:${variant.id}:${d.key}`))
              .map((d) => {
                const label = `${d.style === "white" ? "白底" : "模板"}·原图${d.imgIdx + 1}`;
                const sentinel = `dim:${d.key}`;
                return (
                  <CurationCell
                    key={d.key}
                    {...cellProps(
                      `size_${d.key}` as ImageKey, d.url, label, undefined, true,
                      [{ path: sentinel, url: d.url }],
                      () => deleteDim(d.style, d.imgIdx),
                    )}
                  />
                );
              })}
          </div>
        </div>
      )}

      {active.kind === "library" && (
        <div>
          <div className="text-[11px] opacity-60 mb-2">图片库（{libraryKeys.length}）— 全部图扁平视图 · × 删除</div>
          <div className="grid grid-cols-5 gap-1.5">
            {libraryKeys.map((k) => {
              const o = availableMap.get(k)!;
              const isDim = k.startsWith("size_");
              if (isDim) {
                // size_<style>_img<N>
                const m = k.match(/^size_(white|template)_img(\d+)$/);
                if (m) {
                  const style = m[1]; const imgIdx = parseInt(m[2]);
                  if (undo.isPending(`dim:${variant.id}:${style}_img${imgIdx}`)) return null;
                  const sentinel = `dim:${style}_img${imgIdx}`;
                  return (
                    <CurationCell
                      key={k}
                      {...cellProps(
                        k, o.url, o.label, undefined, true,
                        [{ path: sentinel, url: o.url }],
                        () => deleteDim(style, imgIdx),
                      )}
                    />
                  );
                }
              } else {
                // img<idx>:<ratio>
                const m = k.match(/^img(\d+):(.+)$/);
                if (m) {
                  const idx = parseInt(m[1]); const ratio = m[2];
                  const img = images[idx];
                  const allVersions = (img?.master_history_urls?.[ratio] || []) as MasterVersion[];
                  const versions = allVersions.filter(v => !undo.isPending(v.path));
                  const headPath = (img?.master_paths || {})[ratio];
                  if (headPath && undo.isPending(headPath) && versions.length === 0) return null;
                  return (
                    <CurationCell
                      key={k}
                      {...cellProps(
                        k, o.url, o.label, undefined, false,
                        versions, (p) => img && deleteVersion(img.id, ratio, p, img.name),
                      )}
                    />
                  );
                }
              }
              return (
                <CurationCell key={k} {...cellProps(k, o.url, o.label, undefined, isDim)} />
              );
            })}
          </div>
        </div>
      )}

      {lightbox && (
        <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}

function CurationCell({
  imageKey, url, label, sub, accent,
  cur, isThumb, thumbBusy, onToggleThumb, onZoom,
  versions, onDeleteVersion, deletingPath, imgStatus, onRegenEmpty, isPending,
}: {
  imageKey: ImageKey;
  url?: string;
  label: string;
  sub?: string;
  accent?: boolean;
  cur: ReturnType<typeof useCuration>;
  isThumb: boolean;
  thumbBusy: boolean;
  onToggleThumb: () => void;
  onZoom: (src: string, alt: string) => void;
  versions?: MasterVersion[];
  onDeleteVersion?: (path: string) => void;
  deletingPath?: string | null;
  imgStatus?: string;
  onRegenEmpty?: () => void;
  isPending?: boolean;
}) {
  const inMain = cur.isInMain(imageKey);
  const inDetail = cur.isInDetail(imageKey);
  // versions 顺序：[0]=最新；UI 番号：v1=最旧，v{N}=最新
  const versionList = versions && versions.length > 0 ? versions : (url ? [{ path: "", url }] : []);
  const [activeIdx, setActiveIdx] = useState(0);
  const safeIdx = Math.min(activeIdx, Math.max(0, versionList.length - 1));
  const displayed = versionList[safeIdx];
  const displayedUrl = displayed?.url ?? url;
  const displayedPath = displayed?.path;
  const versionNo = (idx: number) => versionList.length - idx;  // 0→N（最新）; N-1→1（最旧）
  const isGenerating = !url && !!isPending;
  // 已有图但又点了生成 → 旧版本仍展示 + 顶上覆盖一层"vN+1 生成中"
  const regenerating = !!url && !!isPending;
  const nextVersionLabel = `v${versionList.length + 1}`;
  return (
    <div className={`bg-zinc-900 border ${accent ? "border-indigo-700" : isGenerating ? "border-amber-600/60" : "border-zinc-700"} rounded p-1.5`}>
      <div className={`aspect-square rounded mb-1 overflow-hidden relative ${accent ? "bg-white" : "bg-zinc-800"}`}>
        {displayedUrl ? (
          <RatedImage
            src={displayedUrl}
            alt={label}
            className="w-full h-full object-contain"
            onClick={() => onZoom(displayedUrl, label)}
          />
        ) : isGenerating ? (
          <div className="w-full h-full flex flex-col items-center justify-center text-xs text-amber-200/90 gap-1">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
              <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" />
            </svg>
            <span className="text-[10px]">生成中…</span>
            <span className="text-[9px] opacity-60">{label}</span>
          </div>
        ) : onRegenEmpty ? (
          <button
            onClick={onRegenEmpty}
            className="w-full h-full flex flex-col items-center justify-center gap-1 text-xs opacity-50 hover:opacity-100 hover:bg-blue-600/15 transition group/empty"
            title={`生成 ${label}`}
          >
            <span className="text-2xl opacity-60 group-hover/empty:opacity-100">▶</span>
            <span className="text-[10px]">{label}</span>
            <span className="text-[9px] opacity-60">点击生成</span>
          </button>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs opacity-40">{label}</div>
        )}
        {displayedUrl && versionList.length > 1 && (
          <span className="absolute top-0.5 left-0.5 text-[9px] bg-zinc-900/80 text-zinc-100 px-1 rounded">
            v{versionNo(safeIdx)}/{versionList.length}
          </span>
        )}
        {/* 已有图 + 又在生成 → 整张盖一层"vN+1 生成中" */}
        {regenerating && (
          <div className="absolute inset-0 bg-black/55 backdrop-blur-[1px] flex flex-col items-center justify-center text-amber-200 gap-1 pointer-events-none">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
              <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" />
            </svg>
            <span className="text-[11px] font-semibold">{nextVersionLabel} 生成中…</span>
            <span className="text-[9px] opacity-70">旧版仍在下方</span>
          </div>
        )}
        {/* 右上角统一删除按钮：删的是当前展示的那一版 */}
        {displayedUrl && onDeleteVersion && displayedPath && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDeleteVersion(displayedPath);
              // 多版本：删的若是当前激活，跳到下一张
              if (versionList.length > 1) setActiveIdx(0);
            }}
            disabled={deletingPath === displayedPath}
            className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-600/85 hover:bg-red-500 text-white text-[11px] leading-none disabled:opacity-50 z-10"
            title={versionList.length > 1
              ? `删除当前 v${versionNo(safeIdx)}（10s 内可撤销）`
              : "删除该图（10s 内可撤销）"}
          >×</button>
        )}
      </div>
      {/* 版本标签卡：v1 / v2 / v3 ... 点击切换显示，× 删除该版本 */}
      {versionList.length > 1 && (
        <div className="flex gap-1 mb-1 flex-wrap">
          {versionList.map((v, i) => {
            const isActive = i === safeIdx;
            const num = versionNo(i);
            return (
              <span
                key={v.path}
                className={`inline-flex items-center gap-0.5 text-[10px] rounded border transition cursor-pointer ${
                  isActive
                    ? "bg-blue-600 text-white border-blue-500"
                    : "bg-zinc-800 text-zinc-300 border-zinc-700 hover:border-zinc-500"
                }`}
              >
                <span
                  onClick={() => setActiveIdx(i)}
                  className="px-1.5 py-0.5"
                  title={`查看 v${num}${i === 0 ? "（最新）" : ""}`}
                >v{num}{i === 0 && versionList.length > 1 ? " ★" : ""}</span>
                {onDeleteVersion && v.path && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteVersion(v.path);
                      // 如果删的是当前展示的，跳到下一张可用版本
                      if (i === safeIdx) setActiveIdx(0);
                    }}
                    disabled={deletingPath === v.path}
                    className={`px-1 hover:bg-red-600 hover:text-white rounded-r disabled:opacity-50 ${
                      isActive ? "text-white" : "text-zinc-500"
                    }`}
                    title={`删除 v${num}`}
                  >×</button>
                )}
              </span>
            );
          })}
        </div>
      )}
      <div className={`text-[11px] font-semibold truncate ${accent ? "text-indigo-300" : ""}`} title={label}>{label}</div>
      {sub && <div className="text-[9px] opacity-50 line-clamp-1 mb-0.5">{sub}</div>}
      {url && (
        <div className="flex gap-0.5 mt-0.5">
          <button
            onClick={() => cur.toggleMain(imageKey)}
            className={`flex-1 text-[10px] px-0.5 py-0.5 rounded ${
              inMain ? "bg-blue-600 text-white" : "bg-zinc-800 hover:bg-zinc-700"
            }`}
            title="加入主图列表"
          >{inMain ? "✓" : "+"}主</button>
          <button
            onClick={() => cur.toggleDetail(imageKey)}
            className={`flex-1 text-[10px] px-0.5 py-0.5 rounded ${
              inDetail ? "bg-indigo-600 text-white" : "bg-zinc-800 hover:bg-zinc-700"
            }`}
            title="加入详情图列表"
          >{inDetail ? "✓" : "+"}详</button>
          <button
            onClick={onToggleThumb}
            disabled={thumbBusy}
            className={`flex-1 text-[10px] px-0.5 py-0.5 rounded disabled:opacity-50 ${
              isThumb ? "bg-amber-500 text-black" : "bg-zinc-800 hover:bg-zinc-700"
            }`}
            title="加入 SKU 选图列表"
          >{isThumb ? "★" : "☆"}卡</button>
        </div>
      )}
    </div>
  );
}
