"use client";
import { useEffect, useState } from "react";

type SingleProps = { src: string; alt?: string; onClose: () => void; images?: undefined };
type MultiProps = { images: string[]; alt?: string; onClose: () => void; src?: undefined; initialIndex?: number };

/** 支持单图（src）或多图（images + 可选 initialIndex）。多图时按方向键 / 点左右半屏 / 上下两侧按钮切换。 */
export function Lightbox(props: SingleProps | MultiProps) {
  const isMulti = "images" in props && Array.isArray((props as MultiProps).images);
  const list = isMulti ? (props as MultiProps).images : [(props as SingleProps).src];
  const initial = isMulti ? Math.max(0, Math.min(list.length - 1, (props as MultiProps).initialIndex ?? 0)) : 0;
  const [idx, setIdx] = useState(initial);
  const { onClose, alt } = props;

  const prev = () => setIdx((i) => (i - 1 + list.length) % list.length);
  const next = () => setIdx((i) => (i + 1) % list.length);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (list.length > 1 && (e.key === "ArrowLeft")) prev();
      if (list.length > 1 && (e.key === "ArrowRight")) next();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose, list.length]);

  return (
    <div
      className="fixed inset-0 bg-black/92 z-[100] flex items-center justify-center p-6 cursor-zoom-out"
      onClick={onClose}
    >
      <img
        src={list[idx]}
        alt={alt}
        className="max-w-[95vw] max-h-[95vh] object-contain rounded shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />

      {list.length > 1 && (
        <>
          <button
            className="absolute left-4 top-1/2 -translate-y-1/2 bg-zinc-800/80 text-white w-10 h-10 rounded-full text-xl hover:bg-zinc-700 flex items-center justify-center"
            onClick={(e) => { e.stopPropagation(); prev(); }}
          >‹</button>
          <button
            className="absolute right-4 top-1/2 -translate-y-1/2 bg-zinc-800/80 text-white w-10 h-10 rounded-full text-xl hover:bg-zinc-700 flex items-center justify-center"
            onClick={(e) => { e.stopPropagation(); next(); }}
          >›</button>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-black/70 text-white px-3 py-1 rounded text-xs">
            {idx + 1} / {list.length}
          </div>
        </>
      )}

      <button
        className="absolute top-4 right-4 bg-zinc-800/80 text-white px-3 py-1.5 rounded text-sm hover:bg-zinc-700"
        onClick={onClose}
      >关闭 (Esc)</button>
    </div>
  );
}
