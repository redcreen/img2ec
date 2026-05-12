"use client";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useCuration, type ImageKey } from "@/lib/curation";
import type { SourceImage, Variant } from "@/lib/types";
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
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null);
  const [active, setActive] = useState<ActiveTab>({ kind: "image", idx: 0 });
  const [thumbBusy, setThumbBusy] = useState(false);

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

  const [tabBusy, setTabBusy] = useState(false);
  const onDeleteAllForImage = async (img: SourceImage) => {
    if (tabBusy) return;
    if (!confirm(`确认删除「${img.name}」下所有 master 版本？\n（含历史版本 + 派生图，不可撤销）`)) return;
    setTabBusy(true);
    try { await api.deleteAllMastersForImage(pid, sid, img.id); onChanged(); }
    catch (e: any) { alert("批删失败：" + e.message); }
    finally { setTabBusy(false); }
  };
  const onRegenImage = async (img: SourceImage) => {
    if (tabBusy) return;
    // 只重生已有的规格；没有任何已生成则提示去 RatioSelector 选
    const existing = Object.keys(img.master_urls || {});
    if (existing.length === 0) {
      alert(`「${img.name}」还没生成过任何规格。\n请到上方"生成规格"勾选你想要的规格再生成。`);
      return;
    }
    setTabBusy(true);
    try {
      const r = await api.regenerateImage(pid, sid, img.id, { ratios: existing });
      if (r.skipped_in_flight) alert("该图正在生成中，请等当前批跑完再点");
      onChanged();
    } catch (e: any) { alert("提交失败：" + e.message); }
    finally { setTabBusy(false); }
  };
  const onDeleteAllDim = async () => {
    if (tabBusy) return;
    if (!confirm("确认删除该变体下所有尺寸图？\n（不可撤销）")) return;
    setTabBusy(true);
    try { await api.deleteAllDimension(pid, sid, variant.id); onChanged(); }
    catch (e: any) { alert("批删失败：" + e.message); }
    finally { setTabBusy(false); }
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

  const [deletingPath, setDeletingPath] = useState<string | null>(null);
  const deleteVersion = async (imageId: string, ratio: string, path: string) => {
    if (deletingPath) return;
    if (!confirm(`确认删除该版本？\n（文件会从磁盘移除，无法撤销）`)) return;
    setDeletingPath(path);
    try {
      await api.deleteMasterVersion(pid, sid, { image_id: imageId, ratio, path });
      onChanged();
    } catch (e: any) {
      alert("删除失败：" + e.message);
    } finally {
      setDeletingPath(null);
    }
  };
  const deleteDim = async (style: string, imageIdx: number, sentinel: string) => {
    if (deletingPath) return;
    if (!confirm(`确认删除该尺寸图？\n（文件会从磁盘移除，无法撤销）`)) return;
    setDeletingPath(sentinel);
    try {
      await api.deleteDimensionImage(pid, sid, { variant_id: variant.id, style, image_idx: imageIdx });
      onChanged();
    } catch (e: any) {
      alert("删除失败：" + e.message);
    } finally {
      setDeletingPath(null);
    }
  };

  const cellProps = (
    k: ImageKey, url: string | undefined, label: string, sub?: string, accent?: boolean,
    versions?: MasterVersion[],
    onDeleteVersion?: (path: string) => void,
    imgStatus?: string,
  ) => ({
    imageKey: k, url, label, sub, accent,
    cur, isThumb: thumbKeys.includes(k), thumbBusy,
    onToggleThumb: () => toggleThumb(k),
    onZoom: (u: string, alt: string) => setLightbox({ src: u, alt }),
    versions, onDeleteVersion, deletingPath, imgStatus,
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
                const versions = (img.master_history_urls?.[r] || []) as MasterVersion[];
                return (
                  <CurationCell
                    key={r}
                    {...cellProps(
                      `img${idx}:${r}` as ImageKey, img.master_urls?.[r], RATIO_LABEL[r] || r, SHARED_BY[r],
                      false, versions, (p) => deleteVersion(img.id, r, p), img.status,
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
                    const versions = (img.master_history_urls?.[r] || []) as MasterVersion[];
                    return (
                      <CurationCell
                        key={r}
                        {...cellProps(
                          `img${idx}:${r}` as ImageKey, img.master_urls?.[r], RATIO_LABEL[r] || r, SHARED_BY[r],
                          false, versions, (p) => deleteVersion(img.id, r, p), img.status,
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

      {active.kind === "dim" && (
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
            {dimEntries.map((d) => {
              const label = `${d.style === "white" ? "白底" : "模板"}·原图${d.imgIdx + 1}`;
              const sentinel = `dim:${d.key}`;
              return (
                <CurationCell
                  key={d.key}
                  {...cellProps(
                    `size_${d.key}` as ImageKey, d.url, label, undefined, true,
                    [{ path: sentinel, url: d.url }],
                    () => deleteDim(d.style, d.imgIdx, sentinel),
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
                  const sentinel = `dim:${style}_img${imgIdx}`;
                  return (
                    <CurationCell
                      key={k}
                      {...cellProps(
                        k, o.url, o.label, undefined, true,
                        [{ path: sentinel, url: o.url }],
                        () => deleteDim(style, imgIdx, sentinel),
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
                  const versions = (img?.master_history_urls?.[ratio] || []) as MasterVersion[];
                  return (
                    <CurationCell
                      key={k}
                      {...cellProps(
                        k, o.url, o.label, undefined, false,
                        versions, (p) => img && deleteVersion(img.id, ratio, p),
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
  versions, onDeleteVersion, deletingPath, imgStatus,
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
}) {
  const inMain = cur.isInMain(imageKey);
  const inDetail = cur.isInDetail(imageKey);
  // primary (versions[0]) 和 url 一致时用 url；versions 缺失则纯老逻辑
  const versionList = versions && versions.length > 0 ? versions : (url ? [{ path: "", url }] : []);
  const primaryPath = versionList[0]?.path;
  const isGenerating = !url && imgStatus && ["pending", "cutting", "generating", "composing"].includes(imgStatus);
  return (
    <div className={`bg-zinc-900 border ${accent ? "border-indigo-700" : isGenerating ? "border-amber-600/60" : "border-zinc-700"} rounded p-1.5`}>
      <div className={`aspect-square rounded mb-1 overflow-hidden relative ${accent ? "bg-white" : "bg-zinc-800"}`}>
        {url ? (
          <RatedImage
            src={url}
            alt={label}
            className="w-full h-full object-contain"
            onClick={() => onZoom(url, label)}
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
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs opacity-40">{label}</div>
        )}
        {url && versionList.length > 1 && (
          <span className="absolute top-0.5 left-0.5 text-[9px] bg-zinc-900/80 text-zinc-100 px-1 rounded">
            v{versionList.length}/{versionList.length}
          </span>
        )}
        {url && onDeleteVersion && primaryPath && (
          <button
            onClick={(e) => { e.stopPropagation(); onDeleteVersion(primaryPath); }}
            disabled={deletingPath === primaryPath}
            className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-red-600/85 hover:bg-red-500 text-white text-[10px] leading-none disabled:opacity-50"
            title={versionList.length > 1 ? "删除当前版本（下一个版本自动升主）" : "删除该规格图"}
          >×</button>
        )}
      </div>
      {/* 历史版本条（除 primary 之外的旧版） */}
      {versionList.length > 1 && (
        <div className="flex gap-0.5 mb-1 overflow-x-auto pb-0.5">
          {versionList.slice(1).map((v, i) => (
            <div key={v.path} className="relative flex-shrink-0">
              <img
                src={v.url}
                alt=""
                className="w-8 h-8 object-cover rounded border border-zinc-700 cursor-zoom-in opacity-80"
                onClick={() => onZoom(v.url, `${label} v${versionList.length - 1 - i}`)}
                title={`旧版本 v${versionList.length - 1 - i}`}
              />
              {onDeleteVersion && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteVersion(v.path); }}
                  disabled={deletingPath === v.path}
                  className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-red-600/85 hover:bg-red-500 text-white text-[8px] leading-none disabled:opacity-50"
                  title="删除该旧版本"
                >×</button>
              )}
            </div>
          ))}
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
