"use client";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useCuration, type ImageKey } from "@/lib/curation";
import type { Variant } from "@/lib/types";
import { useToast } from "@/lib/useToast";
import { Lightbox } from "./Lightbox";

const RATIO_LABEL: Record<string, string> = {
  "1x1": "1:1", "long": "长图", "3x4": "3:4", "9x16": "9:16", "16x9": "16:9",
  "front": "正面", "side": "侧面", "detail": "细节",
};
const RATIO_ORDER = ["1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"];

interface Opt {
  key: ImageKey;
  url: string;
  label: string;
}

/** 已生成图的操作面板：扁平 grid，每张图三个 toggle（主/详/色卡）+ 点击放大。 */
export function ImageLibraryPanel({
  pid, sid, variant, onChanged,
}: { pid: string; sid: string; variant: Variant; onChanged: () => void }) {
  const cur = useCuration(sid, variant.id);
  const toast = useToast();
  const [thumbBusy, setThumbBusy] = useState(false);
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null);

  const availableMap = useMemo(() => {
    const map = new Map<ImageKey, Opt>();
    variant.images.forEach((img, idx) => {
      for (const [ratio, url] of Object.entries(img.master_urls || {})) {
        if (!url) continue;
        const k: ImageKey = `img${idx}:${ratio}`;
        map.set(k, { key: k, url, label: `${RATIO_LABEL[ratio] || ratio} · 原图${idx + 1}` });
      }
    });
    // 只收 "<style>_img<N>" 的 dim key（旧的纯 "white" / "template" 是兼容别名，过滤掉避免重复）
    for (const [k0, url] of Object.entries(variant.dimension_urls || {})) {
      if (!url) continue;
      const m = k0.match(/^(white|template)_img(\d+)$/);
      if (!m) continue;
      const style = m[1];
      const imgIdx = m[2];
      const key = `size_${k0}`;  // size_white_img0
      map.set(key, {
        key,
        url,
        label: `${style === "white" ? "尺寸图·白底" : "尺寸图·模板"} · 原图${parseInt(imgIdx) + 1}`,
      });
    }
    return map;
  }, [variant.images, variant.dimension_urls]);

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

  // SKU 选图 keys（用文件名匹配）
  const thumbKeys = useMemo<ImageKey[]>(() => {
    if (!variant.sku_thumb_paths?.length) return [];
    return variant.sku_thumb_paths.map((p) => {
      const tail = p.split("/").pop()!;
      for (const [k, opt] of availableMap.entries()) {
        if (decodeURIComponent(opt.url.split("/").pop() || "") === tail) return k;
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
      toast.error("更新 SKU 选图失败：" + e.message);
    } finally {
      setThumbBusy(false);
    }
  };
  const toggleThumb = (k: ImageKey) =>
    setThumbs(thumbKeys.includes(k) ? thumbKeys.filter((x) => x !== k) : [...thumbKeys, k]);
  const reorderThumb = (from: number, to: number) => {
    if (from === to) return;
    const next = [...thumbKeys];
    const [m] = next.splice(from, 1);
    next.splice(to, 0, m);
    setThumbs(next);
  };

  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  if (orderedKeys.length === 0) {
    return (
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
        <div className="text-xs uppercase opacity-50 mb-2">图片库 · {variant.color_name}</div>
        <p className="text-xs opacity-60">该变体还没生成图。先到上方"生成规格"产出 Master。</p>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
      <div className="flex items-center mb-2 gap-2 flex-wrap">
        <h3 className="text-xs uppercase opacity-50">图片库 · {variant.color_name}（{orderedKeys.length}）</h3>
        <span className="text-[10px] opacity-60">点小图放大；每张图三按钮：+主图 / +详情图 / ★SKU 选图</span>
      </div>

      {/* SKU 选图候选已移到平台预览价格上方；此处不再展示 */}
      <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
        {orderedKeys.map((k) => {
          const opt = availableMap.get(k)!;
          const inMain = cur.isInMain(k);
          const inDetail = cur.isInDetail(k);
          const isThumb = thumbKeys.includes(k);
          return (
            <div key={k} className="bg-zinc-950 border border-zinc-700 rounded p-1.5">
              <div className="aspect-square bg-zinc-800 rounded mb-1 overflow-hidden">
                <img
                  src={opt.url}
                  alt={opt.label}
                  className="w-full h-full object-cover cursor-zoom-in hover:opacity-90"
                  loading="lazy"
                  onClick={() => setLightbox({ src: opt.url, alt: opt.label })}
                />
              </div>
              <div className="text-[10px] truncate mb-1" title={opt.label}>{opt.label}</div>
              <div className="flex gap-0.5">
                <button
                  onClick={() => cur.toggleMain(k)}
                  className={`flex-1 text-[10px] px-0.5 py-0.5 rounded ${
                    inMain ? "bg-blue-600 text-white" : "bg-zinc-800 hover:bg-zinc-700"
                  }`}
                  title="加入主图列表"
                >{inMain ? "✓" : "+"}主</button>
                <button
                  onClick={() => cur.toggleDetail(k)}
                  className={`flex-1 text-[10px] px-0.5 py-0.5 rounded ${
                    inDetail ? "bg-indigo-600 text-white" : "bg-zinc-800 hover:bg-zinc-700"
                  }`}
                  title="加入详情图列表"
                >{inDetail ? "✓" : "+"}详</button>
                <button
                  onClick={() => toggleThumb(k)}
                  disabled={thumbBusy}
                  className={`flex-1 text-[10px] px-0.5 py-0.5 rounded disabled:opacity-50 ${
                    isThumb ? "bg-amber-500 text-black" : "bg-zinc-800 hover:bg-zinc-700"
                  }`}
                  title="加入 SKU 选图列表"
                >{isThumb ? "★" : "☆"}卡</button>
              </div>
            </div>
          );
        })}
      </div>
      {lightbox && <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />}
    </div>
  );
}
