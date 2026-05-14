"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useCuration } from "@/lib/curation";
import type { PlatformCopy, SourceImage, Variant } from "@/lib/types";
import { Lightbox } from "./Lightbox";
import { PlatformPreviewMock } from "./PlatformPreviewMock";

const PLATFORMS = ["douyin", "shipinhao", "xiaohongshu"] as const;
type Platform = (typeof PLATFORMS)[number];
const PLATFORM_LABEL: Record<Platform, string> = {
  douyin: "抖店", shipinhao: "视频号", xiaohongshu: "小红书",
};
const PLATFORM_ICON: Record<Platform, string> = {
  douyin: "🛍", shipinhao: "📹", xiaohongshu: "📕",
};
const TITLE_LIMIT: Record<Platform, number> = {
  douyin: 60, shipinhao: 30, xiaohongshu: 20,
};

import type { SKU as SKUType } from "@/lib/types";

export function PlatformTabs({
  pid, skuId, variant, sku, activeVariantId, onSelectVariant, onChanged,
}: {
  pid: string;
  skuId: string;
  variant: Variant;
  sku?: SKUType;
  activeVariantId?: string;
  onSelectVariant?: (vid: string) => void;
  onChanged?: () => void;
}) {
  const images = variant.images;
  const cur = useCuration(skuId, variant.id);
  // copy 没就绪时（数量 < 3）每 3 秒轮询；齐了停轮询节省请求
  const { data: copyList, mutate, isLoading } = useSWR(
    `copy-${skuId}`, () => api.listCopy(skuId),
    {
      refreshInterval: (latest: any) =>
        latest && Array.isArray(latest) && latest.length >= 3 ? 0 : 3000,
    } as any,
  );
  const [activePlatform, setActivePlatform] = useState<Platform>("douyin");
  const [regenerating, setRegenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null);

  const copy = copyList?.find((c) => c.platform === activePlatform);

  const onRegenCopy = async () => {
    setRegenerating(true);
    try {
      await api.regenerateCopy(skuId);
      await mutate();
    } catch (e: any) {
      alert("重新生成失败：" + e.message);
    } finally {
      setRegenerating(false);
    }
  };

  // 只统计真正能下载（在当前 variant 中能解析到 master/dim 文件）的主图
  const resolvableMainCount = (() => {
    let n = 0;
    for (const k of cur.main) {
      if (k.startsWith("size_")) {
        if (variant.dimension_urls?.[k.slice(5)]) n++;
      } else if (k.startsWith("img")) {
        const m = k.match(/^img(\d+):(.+)$/);
        if (!m) continue;
        const idx = parseInt(m[1]); const r = m[2];
        if (variant.images[idx]?.master_urls?.[r]) n++;
      }
    }
    return n;
  })();
  const skuCount = (variant.sku_thumb_paths || []).length;
  const detailReady = !!copy?.detail_template_url;

  const resolvableDetailCount = (() => {
    let n = 0;
    for (const k of cur.detail) {
      if (k.startsWith("size_")) {
        if (variant.dimension_urls?.[k.slice(5)]) n++;
      } else if (k.startsWith("img")) {
        const m = k.match(/^img(\d+):(.+)$/);
        if (!m) continue;
        const idx = parseInt(m[1]); const r = m[2];
        if (variant.images[idx]?.master_urls?.[r]) n++;
      }
    }
    return n;
  })();

  const onDownloadCurrent = async () => {
    setDownloading(true);
    try {
      await api.downloadBundle(pid, skuId, {
        platform: activePlatform,
        variant_id: variant.id,
        main_keys: cur.main,
        detail_keys: cur.detail,
      });
    } catch (e: any) {
      alert(e.message || "下载失败");
    } finally {
      setDownloading(false);
    }
  };
  const onDownloadAll = async () => {
    setDownloading(true);
    try {
      await api.downloadBundleAll(pid, skuId, {
        variant_id: variant.id,
        main_keys: cur.main,
        detail_keys: cur.detail,
      });
    } catch (e: any) {
      alert(e.message || "下载失败");
    } finally {
      setDownloading(false);
    }
  };

  const summaryShared = `主图 ${resolvableMainCount} · SKU 图 ${skuCount} · 详情图 ${resolvableDetailCount}`;
  const canDownload = resolvableMainCount > 0 || skuCount > 0 || resolvableDetailCount > 0 || detailReady;

  const firstImg = images[0];

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded">
      {/* 顶层平台 tab */}
      <div className="flex border-b border-zinc-700">
        {PLATFORMS.map((p) => (
          <button
            key={p}
            onClick={() => setActivePlatform(p)}
            className={`flex-1 text-sm px-4 py-3 font-semibold transition ${
              activePlatform === p
                ? "bg-zinc-800 text-white border-b-2 border-blue-500 -mb-px"
                : "opacity-60 hover:opacity-100 hover:bg-zinc-800/50"
            }`}
          >
            <span className="mr-1.5">{PLATFORM_ICON[p]}</span>
            {PLATFORM_LABEL[p]}
          </button>
        ))}
        <div className="px-3 py-2 flex items-center gap-2">
          <button
            onClick={onRegenCopy}
            disabled={regenerating}
            className="text-xs bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded font-semibold disabled:opacity-50"
            title="文案不满意时重新生成"
          >
            {regenerating ? "重新生成文案中…" : "重新生成文案"}
          </button>
          <button
            onClick={onDownloadAll}
            disabled={downloading || !canDownload}
            className="text-xs bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 rounded font-semibold disabled:opacity-50"
            title={`三平台一并下载（${summaryShared}，各平台一个子目录含详情图+文案）`}
          >
            {downloading ? "打包中…" : `⬇ 下载全平台资料包（${summaryShared}）`}
          </button>
          <button
            onClick={onDownloadCurrent}
            disabled={downloading || !canDownload}
            className="text-xs bg-zinc-700 hover:bg-zinc-600 px-3 py-1.5 rounded font-semibold disabled:opacity-50"
            title={`只下载 ${PLATFORM_LABEL[activePlatform]} 资料：${summaryShared} · 详情图 ${detailReady ? 1 : 0}`}
          >
            {downloading ? "…" : `仅 ${PLATFORM_LABEL[activePlatform]}`}
          </button>
        </div>
      </div>

      {/* 内容：单页面 3 区，宽屏并排，窄屏自动堆叠 */}
      <div className="p-4">
        {!firstImg ? (
          <p className="text-xs opacity-60">无原图</p>
        ) : (
          <div className="flex flex-wrap gap-6 items-start">
            {/* 左：仿平台预览 — 宽度由内容自身决定（≈660px） */}
            <section className="flex-shrink-0">
              <h4 className="text-[10px] uppercase opacity-60 mb-2">仿平台预览</h4>
              {copy ? (
                <PlatformPreviewMock
                  platform={activePlatform}
                  image={firstImg}
                  copy={copy}
                  productId={skuId}
                  variant={variant}
                  pid={pid}
                  sid={skuId}
                  sku={sku}
                  activeVariantId={activeVariantId}
                  onSelectVariant={onSelectVariant}
                  onChanged={() => { mutate(); onChanged?.(); }}
                />
              ) : (
                <p className="text-xs opacity-60">文案未就绪 — 处理完图后会自动生成或点右上"重新生成文案"</p>
              )}
            </section>

            {/* 右：文案（flex，最小 320px） */}
            <section className="flex-1 min-w-[320px] space-y-4">
              <CopySection
                platform={activePlatform}
                copy={copy}
                isLoading={isLoading}
                onZoom={(src) => setLightbox({ src, alt: "detail" })}
              />
            </section>
          </div>
        )}
      </div>

      {lightbox && <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />}
    </div>
  );
}

// ---- sections ----

function CopySection({
  platform, copy, isLoading, onZoom,
}: {
  platform: Platform; copy?: PlatformCopy; isLoading: boolean;
  onZoom: (src: string) => void;
}) {
  if (isLoading) return <div><h4 className="text-[10px] uppercase opacity-60 mb-2">文案</h4><p className="text-xs opacity-60">加载中…</p></div>;
  if (!copy) {
    return (
      <div>
        <h4 className="text-[10px] uppercase opacity-60 mb-2">文案</h4>
        <p className="text-xs opacity-60">暂无文案 — 处理完图后会自动生成。</p>
      </div>
    );
  }

  return (
    <div>
      <h4 className="text-[10px] uppercase opacity-60 mb-2">文案</h4>
      <FieldRow
        label={platform === "xiaohongshu" ? "笔记标题" : "标题"}
        value={copy.title}
        limit={TITLE_LIMIT[platform]}
      />
      {copy.subtitle && <FieldRow label="副标题" value={copy.subtitle} />}
      <ListField label="卖点" items={copy.selling_points} />
      {copy.description_md && (
        <FieldRow
          label={platform === "xiaohongshu" ? "笔记正文" : "详情段落"}
          value={copy.description_md}
        />
      )}
      {copy.video_script && <FieldRow label="30s 视频脚本" value={copy.video_script} />}
      {copy.category_path && <FieldRow label="推荐类目" value={copy.category_path} />}
      {copy.keywords?.length > 0 && <ListField label="关键词" items={copy.keywords} />}
      {copy.hashtags?.length > 0 && <ListField label="Hashtags" items={copy.hashtags} />}
    </div>
  );
}

// ---- shared ----

function FieldRow({ label, value, limit }: { label: string; value: string; limit?: number }) {
  const overLimit = limit !== undefined && value.length > limit;
  return (
    <div className="mb-3">
      <div className="flex items-center text-[10px] uppercase opacity-60 mb-1">
        <span>{label}</span>
        {limit !== undefined && (
          <span className={`ml-2 ${overLimit ? "text-red-400" : ""}`}>
            {value.length}/{limit}
          </span>
        )}
        <button
          onClick={() => navigator.clipboard?.writeText(value)}
          className="ml-auto text-[10px] underline hover:text-white"
        >复制</button>
      </div>
      <div
        className={`text-sm bg-zinc-950 border ${overLimit ? "border-red-700" : "border-zinc-700"} rounded px-3 py-2 break-words whitespace-pre-wrap leading-relaxed`}
      >
        {value || <span className="opacity-40 italic">(empty)</span>}
      </div>
    </div>
  );
}

function ListField({ label, items }: { label: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="mb-3">
      <div className="flex items-center text-[10px] uppercase opacity-60 mb-1">
        <span>{label}</span>
        <span className="ml-2">{items.length} 项</span>
        <button
          onClick={() => navigator.clipboard?.writeText(items.join("\n"))}
          className="ml-auto text-[10px] underline hover:text-white"
        >复制全部</button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span key={i} className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs">{it}</span>
        ))}
      </div>
    </div>
  );
}
