"use client";
import { useState } from "react";

import type { SourceImage } from "@/lib/types";
import { Lightbox } from "./Lightbox";

const PLATFORM_LABEL: Record<string, string> = {
  douyin: "抖店", shipinhao: "视频号", taobao: "淘宝", xiaohongshu: "小红书",
};

const PLATFORM_ORDER = ["douyin", "shipinhao", "taobao", "xiaohongshu"] as const;

function bucketByPlatform(image: SourceImage): Record<string, Array<{ name: string; url: string; key: string }>> {
  const out: Record<string, Array<{ name: string; url: string; key: string }>> = {
    douyin: [], shipinhao: [], taobao: [], xiaohongshu: [],
  };
  for (const [pathKey, url] of Object.entries(image.derived_urls || {})) {
    // pathKey looks like "douyin/test-main-1080x1080.jpg"
    const slash = pathKey.indexOf("/");
    if (slash < 0) continue;
    const platform = pathKey.slice(0, slash);
    const filename = pathKey.slice(slash + 1);
    if (!(platform in out)) continue;
    out[platform].push({ name: filename, url, key: pathKey });
  }
  return out;
}

export function DerivedTable({ images }: { images: SourceImage[] }) {
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null);
  const total = images.reduce((sum, i) => sum + Object.keys(i.derived_urls || {}).length, 0);

  return (
    <div>
      <div className="text-xs uppercase opacity-50 mb-2">平台派生输出（{total} 张）</div>
      {images.map((img) => {
        const buckets = bucketByPlatform(img);
        return (
          <div key={img.id} className="mb-4">
            <div className="text-[11px] opacity-60 mb-2">原图: {img.name}</div>
            {PLATFORM_ORDER.map((p) => {
              const items = buckets[p];
              if (!items || items.length === 0) return null;
              return (
                <div key={p} className="bg-zinc-900 border border-zinc-700 rounded p-3 mb-2">
                  <div className="text-xs font-semibold mb-2">{PLATFORM_LABEL[p]}（{items.length}）</div>
                  <div className="grid grid-cols-4 gap-2">
                    {items.map((it) => (
                      <div key={it.key}>
                        <div
                          className="aspect-square bg-zinc-800 rounded overflow-hidden cursor-zoom-in"
                          onClick={() => setLightbox({ src: it.url, alt: it.name })}
                        >
                          <img src={it.url} alt={it.name} className="w-full h-full object-contain" loading="lazy" />
                        </div>
                        <div className="text-[10px] opacity-55 mt-1 truncate">{it.name}</div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}

      {lightbox && (
        <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}
