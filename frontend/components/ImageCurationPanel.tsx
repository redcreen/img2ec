"use client";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useCuration, type ImageKey } from "@/lib/curation";
import type { SKU, Variant } from "@/lib/types";

const RATIO_LABEL: Record<string, string> = {
  "1x1": "1:1", "long": "长图", "3x4": "3:4", "9x16": "9:16", "16x9": "16:9",
  "front": "正面", "side": "侧面", "detail": "细节",
};
const RATIO_ORDER = ["1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"];

interface ImageOption {
  key: ImageKey;          // 形如 "img0:1x1" / "size_white"
  url: string;
  label: string;          // 显示名："1:1 · 原图1"
  imgIdx?: number;        // 来源原图序号
  ratio?: string;
}

/** 解析旧 key（如 "1x1"）为新 key（如 "img0:1x1"），兼容老 localStorage。 */
function normalizeKey(k: ImageKey): ImageKey {
  if (k.startsWith("img") || k.startsWith("size_")) return k;
  return `img0:${k}`;
}

/** 图片库面板（per variant）：每个变体一份主图列表 + SKU 选图；详情图列表跨变体共享。 */
export function ImageCurationPanel({
  pid, sid, sku, variant, onChanged,
}: { pid: string; sid: string; sku: SKU; variant: Variant; onChanged: () => void }) {
  const cur = useCuration(sid, variant.id);
  const [recomposing, setRecomposing] = useState(false);
  const [thumbBusy, setThumbBusy] = useState(false);

  // 收集变体下所有原图的所有 master + dimension
  const availableMap = useMemo(() => {
    const map = new Map<ImageKey, ImageOption>();
    variant.images.forEach((img, idx) => {
      for (const [ratio, url] of Object.entries(img.master_urls || {})) {
        if (!url) continue;
        const k: ImageKey = `img${idx}:${ratio}`;
        map.set(k, {
          key: k,
          url,
          label: `${RATIO_LABEL[ratio] || ratio} · 原图${idx + 1}`,
          imgIdx: idx,
          ratio,
        });
      }
    });
    // dim 是变体级（不区分原图）
    for (const [style, url] of Object.entries(variant.dimension_urls || {})) {
      if (!url) continue;
      const k = `size_${style}`;
      map.set(k, { key: k, url, label: style === "white" ? "尺寸图·白底" : "尺寸图·模板" });
    }
    return map;
  }, [variant.images, variant.dimension_urls]);

  // 排序：先按原图 idx，再按 ratio 顺序，最后 size_*
  const orderedKeys = useMemo(() => {
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

  // 当前主图/详情 keys，过滤掉不存在的；并把旧 key 形式（"1x1"）规整为 "img0:1x1"
  const mainKeys = cur.main
    .map(normalizeKey)
    .filter((k) => availableMap.has(k));
  const detailKeys = cur.detail
    .map(normalizeKey)
    .filter((k) => availableMap.has(k));

  // SKU 选图列表：从 variant.sku_thumb_paths 反推 keys（文件名匹配）
  const currentThumbKeys = useMemo<ImageKey[]>(() => {
    if (!variant.sku_thumb_paths || variant.sku_thumb_paths.length === 0) return [];
    const out: ImageKey[] = [];
    for (const p of variant.sku_thumb_paths) {
      const pathTail = p.split("/").pop()!;
      for (const [k, opt] of availableMap.entries()) {
        const urlTail = decodeURIComponent(opt.url.split("/").pop() || "");
        if (urlTail === pathTail) {
          out.push(k);
          break;
        }
      }
    }
    return out;
  }, [variant.sku_thumb_paths, availableMap]);

  const recompose = async (keys: ImageKey[]) => {
    if (keys.length === 0) return;
    const hasOneByOne = keys.some((k) => k === "1x1" || k.endsWith(":1x1"));
    if (!hasOneByOne) {
      alert("详情页必须有一张 1:1 主图 — 当前列表里没有任何能解析为 1x1 的图。");
      return;
    }
    setRecomposing(true);
    try {
      await api.composeDetail(pid, sid, variant.id, keys);
      onChanged();
    } catch (e: any) {
      alert("详情页重渲失败：" + e.message);
    } finally {
      setRecomposing(false);
    }
  };

  const saveThumbKeys = async (keys: ImageKey[]) => {
    setThumbBusy(true);
    try {
      await api.setVariantThumbnails(pid, sid, variant.id, keys);
      onChanged();
    } catch (e: any) {
      alert("设置 SKU 选图失败：" + e.message);
    } finally {
      setThumbBusy(false);
    }
  };
  const toggleThumb = (k: ImageKey) => {
    const cur = currentThumbKeys;
    const next = cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k];
    saveThumbKeys(next);
  };
  const reorderThumb = (from: number, to: number) => {
    const next = [...currentThumbKeys];
    const [m] = next.splice(from, 1);
    next.splice(to, 0, m);
    saveThumbKeys(next);
  };

  // 详情图必须含 1×1（首张原图的 1×1）
  const hasOneByOne = detailKeys.some((k) => k.endsWith(":1x1") || k === "1x1");

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
      <div className="flex items-center mb-3 gap-2 flex-wrap">
        <h3 className="text-sm font-semibold">图片库 · 主图 / 详情图 / SKU 选图</h3>
        <span className="text-[11px] opacity-60">勾选展示的图、拖拽排序；详情图改动后点"应用到详情页"重渲</span>
        <div className="flex-1" />
        <button
          onClick={cur.reset}
          className="text-[10px] opacity-60 hover:opacity-100 underline"
        >重置主图&详情列表</button>
      </div>

      {/* 主图列表（per variant） */}
      <Section title={`主图列表（${mainKeys.length}）`} hint="平台预览的主图轮播（per variant）">
        <KeyList
          keys={mainKeys}
          urlOf={(k) => availableMap.get(k)?.url ?? ""}
          labelOf={(k) => availableMap.get(k)?.label ?? k}
          onRemove={cur.toggleMain}
          onReorder={cur.reorderMain}
        />
      </Section>

      {/* 详情图列表（per product） */}
      <Section
        title={`详情图列表（${detailKeys.length}）`}
        hint="产品级 · 跨变体共享 · 多变体自动加颜色对比块"
        action={
          <button
            onClick={() => recompose(detailKeys)}
            disabled={recomposing || detailKeys.length === 0 || !hasOneByOne}
            className="text-xs bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded font-semibold disabled:opacity-40"
          >{recomposing ? "重渲中…" : "▶ 应用到详情页"}</button>
        }
      >
        <KeyList
          keys={detailKeys}
          urlOf={(k) => availableMap.get(k)?.url ?? ""}
          labelOf={(k) => availableMap.get(k)?.label ?? k}
          onRemove={cur.toggleDetail}
          onReorder={cur.reorderDetail}
        />
        {detailKeys.length > 0 && !hasOneByOne && (
          <p className="text-[11px] text-amber-400 mt-1">详情页需要包含某张 1:1 作为 hero</p>
        )}
      </Section>

      {/* SKU 选图列表（per variant，多候选；list[0] = 主色卡） */}
      <Section
        title={`SKU 选图列表（${currentThumbKeys.length}）`}
        hint={`${variant.color_name} · 第 1 张作为色卡主选，其余为备选/A-B`}
      >
        <KeyList
          keys={currentThumbKeys}
          urlOf={(k) => availableMap.get(k)?.url ?? ""}
          labelOf={(k) => availableMap.get(k)?.label ?? k}
          onRemove={toggleThumb}
          onReorder={reorderThumb}
        />
      </Section>

      {/* 所有图 grid */}
      <div className="mt-4">
        <div className="text-[11px] opacity-70 mb-1.5">
          所有已生成的图（{orderedKeys.length}）— 点 + 加入主图/详情，★ 设为 SKU 选图
        </div>
        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2">
          {orderedKeys.map((k) => {
            const opt = availableMap.get(k)!;
            const inMain = cur.isInMain(k) || cur.isInMain(k.replace(/^img\d+:/, ""));
            const inDetail = cur.isInDetail(k) || cur.isInDetail(k.replace(/^img\d+:/, ""));
            const isThumb = currentThumbKeys.includes(k);
            return (
              <div key={k} className="bg-zinc-950 border border-zinc-700 rounded p-1.5">
                <div className="aspect-square bg-zinc-800 rounded mb-1 overflow-hidden">
                  <img src={opt.url} alt={opt.label} className="w-full h-full object-cover" loading="lazy" />
                </div>
                <div className="text-[10px] truncate mb-1" title={opt.label}>{opt.label}</div>
                <div className="flex gap-1">
                  <button
                    onClick={() => cur.toggleMain(k)}
                    className={`flex-1 text-[10px] px-1 py-0.5 rounded ${
                      inMain ? "bg-blue-600 text-white" : "bg-zinc-800 hover:bg-zinc-700"
                    }`}
                  >{inMain ? "✓" : "+"}主</button>
                  <button
                    onClick={() => cur.toggleDetail(k)}
                    className={`flex-1 text-[10px] px-1 py-0.5 rounded ${
                      inDetail ? "bg-indigo-600 text-white" : "bg-zinc-800 hover:bg-zinc-700"
                    }`}
                  >{inDetail ? "✓" : "+"}详</button>
                  <button
                    onClick={() => toggleThumb(k)}
                    disabled={thumbBusy}
                    className={`flex-1 text-[10px] px-1 py-0.5 rounded disabled:opacity-50 ${
                      isThumb ? "bg-amber-500 text-black" : "bg-zinc-800 hover:bg-zinc-700"
                    }`}
                    title="加入/移除 SKU 选图列表"
                  >{isThumb ? "★" : "☆"}</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Section({
  title, hint, action, children,
}: { title: string; hint?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <span className="text-xs font-semibold">{title}</span>
        {hint && <span className="text-[10px] opacity-60">{hint}</span>}
        <div className="flex-1" />
        {action}
      </div>
      {children}
    </div>
  );
}

function KeyList({
  keys, urlOf, labelOf, onRemove, onReorder,
}: {
  keys: ImageKey[];
  urlOf: (k: ImageKey) => string;
  labelOf: (k: ImageKey) => string;
  onRemove: (k: ImageKey) => void;
  onReorder: (from: number, to: number) => void;
}) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  if (keys.length === 0) {
    return <div className="text-[11px] opacity-50 bg-zinc-950 border border-dashed border-zinc-800 rounded p-3">空 — 从下方"所有图"+ 添加</div>;
  }

  return (
    <div className="flex flex-wrap gap-2 bg-zinc-950 border border-zinc-800 rounded p-2">
      {keys.map((k, i) => {
        const url = urlOf(k);
        return (
          <div
            key={k}
            draggable
            onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); setDragFrom(i); }}
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOver(i); }}
            onDragLeave={() => setDragOver((cur) => (cur === i ? null : cur))}
            onDrop={(e) => {
              e.preventDefault();
              const from = parseInt(e.dataTransfer.getData("text/plain"));
              setDragOver(null);
              setDragFrom(null);
              if (!isNaN(from) && from !== i) onReorder(from, i);
            }}
            onDragEnd={() => { setDragFrom(null); setDragOver(null); }}
            className={`relative w-16 group cursor-grab active:cursor-grabbing rounded overflow-hidden border-2 transition ${
              dragOver === i && dragFrom !== null && dragFrom !== i
                ? "border-amber-400 ring-2 ring-amber-400/40"
                : "border-zinc-700"
            } ${dragFrom === i ? "opacity-40" : ""}`}
            title={labelOf(k)}
          >
            <div className="aspect-square bg-zinc-900">
              <img src={url} alt="" className="w-full h-full object-cover pointer-events-none" />
              <span className="absolute top-0 left-0 bg-black/70 text-white text-[9px] px-1 leading-[14px]">{i + 1}</span>
              <button
                onClick={(e) => { e.stopPropagation(); onRemove(k); }}
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-600 text-white text-[10px] leading-none opacity-0 group-hover:opacity-100 hover:bg-red-500"
                title="移除"
              >×</button>
            </div>
            <div className="text-[9px] truncate px-0.5 py-0.5 bg-zinc-900">{labelOf(k)}</div>
          </div>
        );
      })}
    </div>
  );
}
