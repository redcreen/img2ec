"use client";
import { useEffect, useRef, useState } from "react";
import { useRating } from "@/lib/imageRating";

/** 带打分按钮 + 新图 flash 的图片容器。
 * - 鼠标 hover 时显示右上"好/不好"按钮（点击切换）
 * - 第一次渲染（即图片刚生成出现）会有蓝光 flash 提示
 * - "不好"图片整体变灰打 X，提示用户重新生成 */
export function RatedImage({
  src, alt, className, onClick, rateable = true,
}: {
  src: string;
  alt?: string;
  className?: string;
  onClick?: () => void;
  rateable?: boolean;
}) {
  const [rating, setRating] = useRating(src);
  const [flashOn, setFlashOn] = useState(true);
  const firstMount = useRef(true);

  useEffect(() => {
    if (firstMount.current) {
      firstMount.current = false;
      const t = setTimeout(() => setFlashOn(false), 1200);
      return () => clearTimeout(t);
    }
  }, []);

  const toggle = (target: "good" | "bad") => {
    setRating(rating === target ? null : target);
  };

  return (
    <div className={`relative group w-full h-full ${flashOn ? "animate-pulse-flash" : ""}`}>
      <img
        src={src}
        alt={alt}
        onClick={onClick}
        className={`${className || ""} ${
          rating === "bad" ? "opacity-50 grayscale" : ""
        } ${onClick ? "cursor-zoom-in" : ""} transition`}
        loading="lazy"
      />
      {rating === "good" && (
        <div className="absolute top-1 right-1 bg-emerald-500 text-white text-[10px] px-1.5 py-0.5 rounded-full font-bold shadow">
          ✓ 好
        </div>
      )}
      {rating === "bad" && (
        <div className="absolute top-1 right-1 bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full font-bold shadow">
          ✗ 不好
        </div>
      )}
      {rateable && (
        <div className="absolute bottom-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition">
          <button
            onClick={(e) => { e.stopPropagation(); toggle("good"); }}
            className={`text-[11px] w-6 h-6 rounded-full flex items-center justify-center font-bold shadow ${
              rating === "good"
                ? "bg-emerald-500 text-white"
                : "bg-black/70 text-white hover:bg-emerald-600"
            }`}
            title="标记为好"
          >👍</button>
          <button
            onClick={(e) => { e.stopPropagation(); toggle("bad"); }}
            className={`text-[11px] w-6 h-6 rounded-full flex items-center justify-center font-bold shadow ${
              rating === "bad"
                ? "bg-red-500 text-white"
                : "bg-black/70 text-white hover:bg-red-600"
            }`}
            title="标记为不好 — 提示需要重新生成"
          >👎</button>
        </div>
      )}
    </div>
  );
}
