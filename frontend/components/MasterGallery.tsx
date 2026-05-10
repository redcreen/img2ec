"use client";
import { useState } from "react";

import type { SourceImage } from "@/lib/types";
import { Lightbox } from "./Lightbox";

const MASTER_KEYS = ["1x1", "long", "3x4", "9x16", "16x9"] as const;
const RATIO_LABEL: Record<string, string> = {
  "1x1": "1:1", "long": "750w", "3x4": "3:4", "9x16": "9:16", "16x9": "16:9",
};
const SHARED_BY: Record<string, string[]> = {
  "1x1":  ["抖店主图", "视频号主图", "淘宝主图", "小红书 1:1"],
  "long": ["4 平台详情页"],
  "3x4":  ["抖店视频封面", "小红书"],
  "9x16": ["抖店视频封面"],
  "16x9": ["淘宝视频封面"],
};

export function MasterGallery({ images }: { images: SourceImage[] }) {
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null);

  return (
    <div>
      <div className="text-xs uppercase opacity-50 mb-2">
        Master 资产（5/原图 × {images.length} 原图 = {images.length * 5} 张）
      </div>
      {images.map((img, idx) => (
        <div key={img.id} className="mb-4">
          <div className="text-[11px] opacity-60 mb-2">原图 {idx + 1}: {img.name}</div>
          <div className="grid grid-cols-5 gap-2">
            {MASTER_KEYS.map((k) => {
              const url = img.master_urls?.[k];
              const ratio = RATIO_LABEL[k];
              return (
                <div key={k} className="bg-zinc-900 border border-zinc-700 rounded p-2">
                  <div
                    className="aspect-square bg-zinc-800 rounded mb-2 flex items-center justify-center cursor-zoom-in overflow-hidden"
                    onClick={() => url && setLightbox({ src: url, alt: `${img.name} ${k}` })}
                  >
                    {url ? (
                      <img src={url} alt={k} className="w-full h-full object-contain" loading="lazy" />
                    ) : (
                      <span className="text-xs opacity-40">{ratio}</span>
                    )}
                  </div>
                  <div className="text-[11px] font-semibold">{ratio}</div>
                  <div className="text-[10px] opacity-55 line-clamp-2 mt-0.5">
                    {SHARED_BY[k]?.slice(0, 2).join("、")}
                    {SHARED_BY[k]?.length > 2 ? "…" : ""}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {lightbox && (
        <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}
