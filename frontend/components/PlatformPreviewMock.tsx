"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { mutate as globalMutate } from "swr";
import type { PlatformCopy, SourceImage, Variant, SKU } from "@/lib/types";
import { api } from "@/lib/api";
import { Lightbox } from "./Lightbox";
import { useCuration } from "@/lib/curation";

type Platform = "douyin" | "shipinhao" | "xiaohongshu";

const PHONE_WIDTH = 320;
const PHONE_HEIGHT = 720;

// 主图列表现在由 useCuration 提供（per-SKU，跨平台一致）。本组件只读，
// 编辑由 ImageCurationPanel 完成。

/** 仿平台预览：上方多图缩略横排（来自 useCuration 主图列表，per variant）。 */
export function PlatformPreviewMock({
  platform, image, copy, productId, variant, pid, sid, sku, activeVariantId, onSelectVariant, onChanged,
}: {
  platform: Platform;
  image: SourceImage;
  copy: PlatformCopy;
  productId: string;
  variant: Variant;
  pid: string;
  sid: string;
  sku?: SKU;
  activeVariantId?: string;
  onSelectVariant?: (vid: string) => void;
  onChanged: () => void;
}) {
  const cur = useCuration(productId, variant.id);

  // 支持 img<idx>:<ratio> / size_<style> / 旧式 <ratio>（兼容 = img0:ratio）
  const resolve = (k: string): string | undefined => {
    if (k.startsWith("size_")) {
      // k = "size_white_img0" → 取 "white_img0"
      const styleKey = k.slice(5);
      return variant.dimension_urls?.[styleKey];
    }
    if (k.startsWith("img")) {
      const m = k.match(/^img(\d+):(.+)$/);
      if (!m) return undefined;
      const idx = parseInt(m[1]);
      const ratio = m[2];
      return variant.images[idx]?.master_urls?.[ratio];
    }
    // legacy: 当 ratio 解析，绑 img0
    return variant.images[0]?.master_urls?.[k];
  };

  const visibleItems = useMemo(() => {
    const out: Array<{ key: string; url: string }> = [];
    const seen = new Set<string>();
    for (const k of cur.main) {
      const url = resolve(k);
      if (url && !seen.has(url)) {
        out.push({ key: k, url });
        seen.add(url);
      }
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur.main.join("|"), variant.images.map(i => Object.keys(i.master_urls || {}).join(",")).join("|"), variant.dimension_urls]);
  const visibleImages = visibleItems.map((it) => it.url);

  const heroUrl =
    visibleImages[0] ??
    image.master_urls?.["1x1"] ??
    Object.values(image.master_urls ?? {})[0] ??
    image.src_url ??
    null;

  const [idx, setIdx] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [detailLightbox, setDetailLightbox] = useState(false);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  /** 拖拽缩略：把 visibleItems[from] 移到 visibleItems[to]，映射回 cur.main 的全局 index 调用 reorderMain */
  const reorderThumbs = (from: number, to: number) => {
    if (from === to) return;
    const movedKey = visibleItems[from]?.key;
    const targetKey = visibleItems[to]?.key;
    if (!movedKey || !targetKey) return;
    const fromIdx = cur.main.indexOf(movedKey);
    const toIdx = cur.main.indexOf(targetKey);
    if (fromIdx < 0 || toIdx < 0) return;
    cur.reorderMain(fromIdx, toIdx);
    // 保持视觉焦点跟随被拖的那张
    setIdx(to);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (lightboxOpen || detailLightbox) return;
      const tag = (document.activeElement as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (visibleImages.length < 2) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIdx((i) => (i - 1 + visibleImages.length) % visibleImages.length);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setIdx((i) => (i + 1) % visibleImages.length);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visibleImages.length, lightboxOpen, detailLightbox]);

  useEffect(() => { setIdx(0); }, [platform, image.id]);

  // 当前变体的 SKU 选图候选（多张）：在预览中作为色卡条，点击换 hero
  const skuCandidates = variant.sku_thumb_urls ?? [];
  const [activeCandidateIdx, setActiveCandidateIdx] = useState<number | null>(null);
  useEffect(() => { setActiveCandidateIdx(null); }, [variant.id]);

  // 跨变体（备用）：单变体时不显示
  const variantSwatches = useMemo(() => {
    if (!sku || sku.variants.length < 2) return [];
    return sku.variants.map((v) => ({
      id: v.id,
      name: v.color_name,
      url: v.sku_thumb_url || v.images[0]?.master_urls?.["1x1"] || null,
    }));
  }, [sku?.variants]);

  // 详情图列表
  const detailItems = useMemo<Array<{ key: string; url: string }>>(() => {
    const out: Array<{ key: string; url: string }> = [];
    for (const k of cur.detail) {
      const url = resolve(k);
      if (url) out.push({ key: k, url });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur.detail.join("|"), variant.images, variant.dimension_urls]);

  const [composing, setComposing] = useState(false);
  const applyDetail = async (keys?: string[]) => {
    const ks = keys ?? detailItems.map((it) => it.key);
    if (ks.length === 0) return;
    setComposing(true);
    try {
      await api.composeDetail(pid, sid, ks);
      // 详情图 URL 不变（固定路径），需要触发 copy SWR 重取以拿到带新 ?t=<mtime> 的 URL
      globalMutate(`copy-${sid}`);
      onChanged();
    } catch (e: any) {
      alert("应用到详情页失败：" + e.message);
    } finally {
      setComposing(false);
    }
  };

  const composeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const detailKey = cur.detail.join("|");
  const lastAppliedRef = useRef<string>("");
  useEffect(() => {
    if (detailKey === lastAppliedRef.current) return;
    if (composeTimerRef.current) clearTimeout(composeTimerRef.current);
    composeTimerRef.current = setTimeout(() => {
      if (detailItems.length > 0) {
        lastAppliedRef.current = detailKey;
        applyDetail(detailItems.map((it) => it.key));
      }
    }, 600);
    return () => { if (composeTimerRef.current) clearTimeout(composeTimerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailKey]);

  // ---- 所有 hooks 已声明完毕；下面是计算 / 早退 ----
  if (!heroUrl) {
    return <p className="text-xs opacity-60">主图未生成 — 先到上方生成 1:1 主图</p>;
  }

  const candidateHero = activeCandidateIdx !== null ? skuCandidates[activeCandidateIdx] : null;
  const currentUrl = candidateHero ?? (visibleImages[Math.min(idx, visibleImages.length - 1)] ?? heroUrl);
  const detailUrl = copy.detail_template_url ?? null;

  const reorderCandidate = async (from: number, to: number) => {
    if (from === to) return;
    const paths = [...(variant.sku_thumb_paths ?? [])];
    const [m] = paths.splice(from, 1);
    paths.splice(to, 0, m);
    // 反推 keys
    const keys = paths.map((p) => {
      const tail = p.split("/").pop()!;
      for (let i = 0; i < variant.images.length; i++) {
        const mu = variant.images[i].master_urls || {};
        for (const [r, u] of Object.entries(mu)) {
          if (u && decodeURIComponent(u.split("/").pop() || "") === tail) return `img${i}:${r}`;
        }
      }
      for (const [styleKey, u] of Object.entries(variant.dimension_urls || {})) {
        if (u && decodeURIComponent(u.split("/").pop() || "") === tail) return `size_${styleKey}`;
      }
      return "";
    }).filter(Boolean) as string[];
    if (keys.length !== paths.length) return;
    try {
      await api.setVariantThumbnails(pid, sid, variant.id, keys);
      onChanged();
    } catch (e: any) {
      alert("色卡排序失败：" + e.message);
    }
  };

  const mockProps: MockProps = {
    currentUrl,
    copy,
    totalImages: visibleImages.length,
    currentIndex: idx + 1,
    onHeroClick: () => setLightboxOpen(true),
    skuCandidates,
    activeCandidateIdx,
    onSelectCandidate: (i) => setActiveCandidateIdx(i),
    onReorderCandidate: reorderCandidate,
  };

  return (
    <div>
      {/* 顶部：主图列表缩略 — 拖拽排序、× 删除、键盘 ← → 切换 */}
      {visibleItems.length > 0 && (
        <div className="mb-3 flex items-center gap-2 flex-wrap">
          <span className="text-[10px] opacity-60">
            主图（{idx + 1}/{visibleItems.length}） · 拖拽排序 · 键盘 ← → · 点 × 删除
          </span>
          <div className="flex gap-1.5 overflow-x-auto pb-1 flex-1">
            {visibleItems.map((it, i) => (
              <div key={it.url} className="relative group flex-shrink-0">
                <button
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", String(i));
                    setDragFrom(i);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    setDragOver(i);
                  }}
                  onDragLeave={() => setDragOver((c) => (c === i ? null : c))}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(null);
                    setDragFrom(null);
                    const from = parseInt(e.dataTransfer.getData("text/plain"));
                    if (!isNaN(from)) reorderThumbs(from, i);
                  }}
                  onDragEnd={() => { setDragFrom(null); setDragOver(null); }}
                  onClick={() => setIdx(i)}
                  className={`relative w-14 h-14 rounded overflow-hidden border-2 transition cursor-grab active:cursor-grabbing ${
                    dragOver === i && dragFrom !== null && dragFrom !== i
                      ? "border-amber-400 ring-2 ring-amber-400/40"
                      : i === idx
                      ? "border-blue-500 ring-2 ring-blue-500/30"
                      : "border-zinc-700 hover:border-zinc-500 opacity-80 hover:opacity-100"
                  } ${dragFrom === i ? "opacity-40" : ""}`}
                  title={`第 ${i + 1} 张 · 拖动调整顺序`}
                >
                  <img src={it.url} alt="" className="w-full h-full object-cover pointer-events-none" />
                  <span className="absolute top-0 left-0 bg-black/70 text-white text-[9px] px-1 leading-[14px]">{i + 1}</span>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); cur.toggleMain(it.key); }}
                  className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-600 text-white text-[10px] leading-none opacity-0 group-hover:opacity-100 transition hover:bg-red-500"
                  title="从主图列表移除（保留在图片库，可再次加入）"
                >×</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 两个手机并排：左 listing / 右 详情 */}
      <div className="flex gap-4 items-start flex-wrap">
        <div className="flex flex-col items-center">
          {platform === "douyin" && <DouyinMock {...mockProps} />}
          {platform === "shipinhao" && <ShipinhaoMock {...mockProps} />}
          {platform === "xiaohongshu" && <XiaohongshuMock {...mockProps} />}
          <div className="text-[10px] opacity-50 mt-2">商品 listing</div>
        </div>

        <div className="flex flex-col items-center" style={{ width: PHONE_WIDTH }}>
          {detailUrl ? (
            <DetailPhone
              url={detailUrl}
              theme={platform === "xiaohongshu" ? "light" : "dark"}
              onFullscreen={() => setDetailLightbox(true)}
            />
          ) : (
            <div
              className="border-[10px] border-zinc-700 rounded-[2.5rem] bg-zinc-900 flex items-center justify-center text-xs opacity-60 px-6 text-center"
              style={{ width: PHONE_WIDTH, height: PHONE_HEIGHT }}
            >
              详情页拼图未生成<br />（生成 master 后会自动产出）
            </div>
          )}
          {/* 详情图列表 inline 控制（产品级） */}
          <div className="mt-3 w-full">
            <div className="flex items-center mb-1.5">
              <span className="text-[10px] opacity-60">
                详情图列表（{detailItems.length}）· 拖拽排序 · × 移除
              </span>
              <div className="flex-1" />
              <button
                onClick={() => applyDetail()}
                disabled={composing || detailItems.length === 0}
                className="text-[10px] bg-blue-600 hover:bg-blue-500 px-2 py-0.5 rounded font-semibold disabled:opacity-40"
              >{composing ? "重渲中…" : "应用到详情页"}</button>
            </div>
            <DetailListStrip
              items={detailItems}
              onReorder={cur.reorderDetail}
              onRemove={(k) => cur.toggleDetail(k)}
            />
          </div>
        </div>
      </div>

      {lightboxOpen && (
        <Lightbox
          images={visibleImages}
          initialIndex={idx}
          alt="平台图片"
          onClose={() => setLightboxOpen(false)}
        />
      )}
      {detailLightbox && detailUrl && (
        <Lightbox src={detailUrl} alt="详情页拼图" onClose={() => setDetailLightbox(false)} />
      )}
    </div>
  );
}

interface MockProps {
  currentUrl: string;
  copy: PlatformCopy;
  totalImages: number;
  currentIndex: number;
  onHeroClick: () => void;
  skuCandidates: string[];
  activeCandidateIdx: number | null;
  onSelectCandidate: (i: number | null) => void;
  onReorderCandidate: (from: number, to: number) => void;
}

/** 详情图列表条（产品级 · 拖拽排序 · × 移除）。 */
function DetailListStrip({
  items, onReorder, onRemove,
}: {
  items: Array<{ key: string; url: string }>;
  onReorder: (from: number, to: number) => void;
  onRemove: (k: string) => void;
}) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);
  if (items.length === 0) {
    return (
      <div className="text-[10px] opacity-50 bg-zinc-950 border border-dashed border-zinc-800 rounded p-2">
        空 — 在右侧 Master 库给图片点 "+详" 加入
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5 bg-zinc-950 border border-zinc-800 rounded p-1.5">
      {items.map((it, i) => (
        <div key={`${it.key}:${i}`} className="relative group">
          <div
            draggable
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = "move";
              e.dataTransfer.setData("text/plain", String(i));
              setDragFrom(i);
            }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(i); }}
            onDragLeave={() => setDragOver((c) => (c === i ? null : c))}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(null); setDragFrom(null);
              const from = parseInt(e.dataTransfer.getData("text/plain"));
              if (!isNaN(from) && from !== i) onReorder(from, i);
            }}
            onDragEnd={() => { setDragFrom(null); setDragOver(null); }}
            className={`w-10 h-10 rounded border cursor-grab active:cursor-grabbing overflow-hidden ${
              dragOver === i && dragFrom !== null && dragFrom !== i
                ? "border-amber-400 ring-1 ring-amber-400/60"
                : "border-zinc-700"
            } ${dragFrom === i ? "opacity-40" : ""}`}
            title={`第 ${i + 1} 张 · 拖拽改顺序`}
          >
            <img src={it.url} alt="" className="w-full h-full object-cover pointer-events-none" />
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(it.key); }}
            className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-red-600 text-white text-[9px] leading-none opacity-0 group-hover:opacity-100 hover:bg-red-500"
            title="从详情图列表移除"
          >×</button>
        </div>
      ))}
    </div>
  );
}

/** 当前变体 SKU 选图候选条：撑满预览宽度，点击换 hero（再点取消），拖拽改顺序。 */
function CandidateStrip({
  urls, activeIdx, onSelect, onReorder,
}: {
  urls: string[];
  activeIdx: number | null;
  onSelect: (i: number | null) => void;
  onReorder: (from: number, to: number) => void;
}) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);
  if (urls.length === 0) return null;
  return (
    <div className="w-full">
      <div className="text-[10px] opacity-70 mb-1">
        SKU 选图（{urls.length}）· 点击换图 · 再点取消 · 拖拽排序
      </div>
      <div className="flex gap-1.5 w-full overflow-x-auto pb-1">
        {urls.map((u, i) => {
          const active = i === activeIdx;
          return (
            <button
              key={`${u}:${i}`}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", String(i));
                setDragFrom(i);
              }}
              onDragOver={(e) => { e.preventDefault(); setDragOver(i); }}
              onDragLeave={() => setDragOver((c) => (c === i ? null : c))}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(null); setDragFrom(null);
                const from = parseInt(e.dataTransfer.getData("text/plain"));
                if (!isNaN(from) && from !== i) onReorder(from, i);
              }}
              onDragEnd={() => { setDragFrom(null); setDragOver(null); }}
              onClick={() => onSelect(active ? null : i)}
              className={`flex-shrink-0 w-12 h-12 rounded border-2 overflow-hidden transition cursor-grab active:cursor-grabbing relative ${
                dragOver === i && dragFrom !== null && dragFrom !== i
                  ? "border-amber-400 ring-2 ring-amber-400/40"
                  : active
                  ? "border-amber-400 ring-2 ring-amber-400/40"
                  : "border-zinc-600 hover:border-zinc-400 opacity-80 hover:opacity-100"
              } ${dragFrom === i ? "opacity-40" : ""}`}
              title={`候选 ${i + 1}${i === 0 ? "（主色卡）" : ""} · 点击切换 / 拖拽`}
            >
              <img src={u} alt="" className="w-full h-full object-cover pointer-events-none" />
              {i === 0 && (
                <span className="absolute top-0 left-0 bg-amber-500 text-black text-[8px] px-0.5 leading-tight font-bold">主</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PhoneFrame({
  children, theme = "dark",
}: { children: React.ReactNode; theme?: "dark" | "light" }) {
  return (
    <div
      className={`rounded-[2.5rem] border-[10px] border-zinc-700 shadow-2xl overflow-hidden ${
        theme === "dark" ? "bg-black text-white" : "bg-white text-zinc-900"
      }`}
      style={{ width: PHONE_WIDTH }}
    >
      <div className="overflow-y-auto" style={{ height: PHONE_HEIGHT }}>
        {children}
      </div>
    </div>
  );
}

/** 右侧"详情"手机：状态栏 + 长图（内置滚动）。 */
function DetailPhone({
  url, theme, onFullscreen,
}: { url: string; theme: "dark" | "light"; onFullscreen: () => void }) {
  return (
    <PhoneFrame theme={theme}>
      <div className={theme === "dark" ? "bg-zinc-950" : "bg-white"}>
        <div
          className={`flex items-center justify-between px-4 py-2 text-[10px] sticky top-0 z-10 ${
            theme === "dark" ? "bg-zinc-950 opacity-90" : "bg-white border-b border-zinc-100"
          }`}
        >
          <button className="text-base">←</button>
          <span className="font-semibold">商品详情</span>
          <span>⋯</span>
        </div>
        <img
          src={url}
          alt="详情页"
          className="w-full block cursor-zoom-in hover:opacity-95"
          onClick={onFullscreen}
        />
      </div>
    </PhoneFrame>
  );
}

function DouyinMock({ currentUrl, copy, totalImages, currentIndex, onHeroClick, skuCandidates, activeCandidateIdx, onSelectCandidate, onReorderCandidate }: MockProps) {
  return (
    <PhoneFrame theme="dark">
      <div className="bg-zinc-950">
        <div className="flex items-center justify-between px-4 py-2 text-[10px] opacity-70 sticky top-0 bg-zinc-950 z-10">
          <span>9:41</span>
          <span>抖店</span>
          <span>📶 100%</span>
        </div>
        <div className="aspect-square bg-zinc-900 relative cursor-zoom-in" onClick={onHeroClick}>
          <img src={currentUrl} className="w-full h-full object-cover" alt="" />
          <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-0.5 rounded text-[10px]">
            {currentIndex}/{totalImages}
          </div>
        </div>
        <div className="px-3 py-3 bg-black">
          {skuCandidates.length > 0 && (
            <div className="mb-2">
              <CandidateStrip
                urls={skuCandidates}
                activeIdx={activeCandidateIdx}
                onSelect={onSelectCandidate}
                onReorder={onReorderCandidate}
              />
            </div>
          )}
          <div className="flex items-baseline gap-1">
            <span className="text-rose-500 text-2xl font-bold">¥99</span>
            <span className="text-zinc-500 text-xs line-through">¥199</span>
            <span className="ml-auto text-[10px] bg-rose-600 px-1.5 py-0.5 rounded">5折</span>
          </div>
          <h3 className="text-sm font-bold mt-2 leading-snug">{copy.title}</h3>
          {copy.subtitle && (
            <p className="text-[11px] opacity-70 mt-1">{copy.subtitle}</p>
          )}
        </div>
        {copy.selling_points?.length > 0 && (
          <div className="px-3 py-2 bg-zinc-900 border-t border-zinc-800 space-y-1.5">
            {copy.selling_points.slice(0, 3).map((p, i) => (
              <div key={i} className="flex gap-2 items-start text-[11px]">
                <span className="text-rose-400">✓</span>
                <span className="opacity-90 leading-snug">{p}</span>
              </div>
            ))}
          </div>
        )}
        <div className="px-3 py-3 flex gap-2 bg-black border-t border-zinc-900">
          <button className="flex-1 bg-amber-500 text-black py-2 rounded-full text-xs font-bold">加入购物车</button>
          <button className="flex-1 bg-rose-600 text-white py-2 rounded-full text-xs font-bold">立即购买</button>
        </div>
      </div>
    </PhoneFrame>
  );
}

function ShipinhaoMock({ currentUrl, copy, totalImages, currentIndex, onHeroClick, skuCandidates, activeCandidateIdx, onSelectCandidate, onReorderCandidate }: MockProps) {
  // 微信小店 layout：浅色 + 微信绿，结构对齐抖店（图 → SKU 选图 → 价格 → 标题 → 卖点 → CTA）
  return (
    <PhoneFrame theme="light">
      <div className="bg-zinc-50 text-zinc-900">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-zinc-100 sticky top-0 z-10">
          <button className="text-base">←</button>
          <span className="text-xs font-semibold">商品详情</span>
          <span className="text-base">⋯</span>
        </div>
        {/* hero */}
        <div className="aspect-square bg-white relative cursor-zoom-in" onClick={onHeroClick}>
          <img src={currentUrl} className="w-full h-full object-cover" alt="" />
          <div className="absolute bottom-2 right-2 bg-black/60 text-white px-2 py-0.5 rounded text-[10px]">
            {currentIndex}/{totalImages}
          </div>
        </div>
        {/* SKU 选图 + 价格 + 标题 */}
        <div className="px-3 py-3 bg-white">
          {skuCandidates.length > 0 && (
            <div className="mb-2.5">
              <CandidateStrip
                urls={skuCandidates}
                activeIdx={activeCandidateIdx}
                onSelect={onSelectCandidate}
                onReorder={onReorderCandidate}
              />
            </div>
          )}
          <div className="flex items-baseline gap-1">
            <span className="text-[11px] text-rose-600 font-semibold">¥</span>
            <span className="text-rose-600 text-2xl font-bold leading-none">99</span>
            <span className="text-zinc-400 text-xs line-through ml-1">¥199</span>
            <span className="ml-auto text-[10px] bg-emerald-500 text-white px-1.5 py-0.5 rounded">微信支付优惠</span>
          </div>
          <h3 className="text-sm font-bold mt-2 leading-snug">{copy.title}</h3>
          {copy.subtitle && (
            <p className="text-[11px] text-zinc-500 mt-1">{copy.subtitle}</p>
          )}
          <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-2">
            <span>📦 包邮</span>
            <span>·</span>
            <span>🛡 7 天无理由</span>
            <span>·</span>
            <span>月销 200+</span>
          </div>
        </div>
        {/* 卖点 */}
        {copy.selling_points?.length > 0 && (
          <div className="px-3 py-2.5 mt-1.5 bg-white border-t border-zinc-100 space-y-1.5">
            {copy.selling_points.slice(0, 3).map((p, i) => (
              <div key={i} className="flex gap-2 items-start text-[11px]">
                <span className="text-emerald-600">✓</span>
                <span className="text-zinc-700 leading-snug">{p}</span>
              </div>
            ))}
          </div>
        )}
        {/* 店铺信息 */}
        <div className="px-3 py-2.5 mt-1.5 bg-white border-t border-zinc-100 flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-emerald-100 flex items-center justify-center text-emerald-700 text-[11px] font-bold">店</div>
          <div className="text-[11px] flex-1">
            <div className="font-semibold text-zinc-800">商家小店</div>
            <div className="text-[10px] text-zinc-500">微信小店 · 1.2k 粉丝</div>
          </div>
          <button className="text-[10px] border border-emerald-500 text-emerald-600 px-3 py-1 rounded-full font-semibold">进店</button>
        </div>
        {/* CTA */}
        <div className="px-3 py-3 flex gap-2 bg-white border-t border-zinc-100 sticky bottom-0">
          <button className="w-9 h-9 flex flex-col items-center justify-center text-[9px] text-zinc-600">
            <span className="text-base leading-none">💬</span>客服
          </button>
          <button className="w-9 h-9 flex flex-col items-center justify-center text-[9px] text-zinc-600">
            <span className="text-base leading-none">🏪</span>店铺
          </button>
          <button className="flex-1 border border-emerald-500 text-emerald-600 py-2 rounded-full text-xs font-bold">加入购物车</button>
          <button className="flex-1 bg-emerald-500 text-white py-2 rounded-full text-xs font-bold">立即购买</button>
        </div>
      </div>
    </PhoneFrame>
  );
}

function XiaohongshuMock({ currentUrl, copy, totalImages, currentIndex, onHeroClick, skuCandidates, activeCandidateIdx, onSelectCandidate, onReorderCandidate }: MockProps) {
  return (
    <PhoneFrame theme="light">
      <div className="bg-white">
        <div className="flex items-center px-3 py-2 border-b border-zinc-100 sticky top-0 bg-white z-10">
          <button className="text-lg">←</button>
          <div className="flex-1" />
          <button className="text-rose-500 text-xs font-semibold">+ 关注</button>
        </div>
        <div className="flex items-center px-3 py-2 gap-2">
          <div className="w-9 h-9 rounded-full bg-rose-200" />
          <div className="text-xs flex-1">
            <div className="font-bold">小红书博主</div>
            <div className="text-[10px] opacity-50">5 分钟前</div>
          </div>
        </div>
        <div className="aspect-square bg-zinc-100 relative cursor-zoom-in" onClick={onHeroClick}>
          <img src={currentUrl} className="w-full h-full object-cover" alt="" />
          <div className="absolute top-2 right-2 bg-black/60 text-white px-2 py-0.5 rounded text-[10px]">
            {currentIndex}/{totalImages}
          </div>
        </div>
        <div className="px-3 py-3">
          <h3 className="text-base font-bold leading-snug mb-1.5">{copy.title}</h3>
          {copy.description_md && (
            <p className="text-[11px] leading-relaxed whitespace-pre-wrap">
              {copy.description_md}
            </p>
          )}
          {copy.hashtags?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {copy.hashtags.slice(0, 6).map((t, i) => (
                <span key={i} className="text-[11px] text-blue-600">#{t.replace(/^#/, "")}</span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-4 text-[11px] mt-3 pt-3 border-t border-zinc-100">
            <span>❤ 1.2k</span>
            <span>💬 88</span>
            <span>⭐ 320</span>
          </div>
        </div>
      </div>
    </PhoneFrame>
  );
}
