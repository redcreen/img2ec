"use client";
import { useEffect } from "react";

export function Lightbox({
  src, alt, onClose,
}: { src: string; alt?: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-6 cursor-zoom-out"
      onClick={onClose}
    >
      <img
        src={src}
        alt={alt}
        className="max-w-[95vw] max-h-[95vh] object-contain rounded shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
      <button
        className="absolute top-4 right-4 bg-zinc-800/80 text-white px-3 py-1.5 rounded text-sm hover:bg-zinc-700"
        onClick={onClose}
      >关闭 (Esc)</button>
    </div>
  );
}
