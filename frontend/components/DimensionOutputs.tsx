"use client";
import { useState } from "react";
import type { Variant } from "@/lib/types";
import { Lightbox } from "./Lightbox";
import { RatedImage } from "./RatedImage";

const STYLES = [
  { key: "white", label: "白底尺寸图" },
  { key: "template", label: "模板尺寸图" },
] as const;

/** 尺寸图输出区（per variant）。 */
export function DimensionOutputs({ variant }: { variant: Variant }) {
  const [lightbox, setLightbox] = useState<string | null>(null);
  const urls = variant.dimension_urls ?? {};
  const states = variant.dimension_states ?? {};
  const anyExist = Object.values(urls).some(Boolean);
  const anyGenerating = Object.values(states).some((s) => s?.status === "generating");

  if (!anyExist && !anyGenerating) return null;

  return (
    <div>
      <div className="text-xs uppercase opacity-50 mb-2">
        尺寸图（{Object.keys(urls).length}/2 已生成）
      </div>
      <div className="flex flex-wrap gap-3">
        {STYLES.map((s) => {
          const url = urls[s.key];
          const st = states[s.key]?.status;
          return (
            <div key={s.key} className="bg-zinc-900 border border-zinc-700 rounded p-2 w-[180px]">
              <div className="text-[10px] opacity-70 mb-1 flex items-center gap-1.5">
                <span>{s.label}</span>
                {st === "generating" && <span className="text-amber-400">生成中…</span>}
                {st === "error" && <span className="text-red-400">失败</span>}
              </div>
              <div className="aspect-square bg-zinc-800 rounded overflow-hidden">
                {url ? (
                  <RatedImage
                    src={url}
                    alt={s.label}
                    className="w-full h-full object-contain bg-white"
                    onClick={() => setLightbox(url)}
                  />
                ) : st === "generating" ? (
                  <div className="w-full h-full flex items-center justify-center text-[10px] opacity-50 text-center px-2">
                    Codex 生成中…(~50s)
                  </div>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[10px] opacity-40">
                    未生成
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {lightbox && <Lightbox src={lightbox} alt="尺寸图" onClose={() => setLightbox(null)} />}
    </div>
  );
}
