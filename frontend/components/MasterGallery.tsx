import type { SourceImage } from "@/lib/types";

const MASTER_RATIOS: Array<{ key: string; ratio: string; sharedBy: string[] }> = [
  { key: "1x1",  ratio: "1:1",  sharedBy: ["抖店主图", "视频号主图", "淘宝主图", "小红书 1:1"] },
  { key: "long", ratio: "750w", sharedBy: ["4 平台详情页"] },
  { key: "3x4",  ratio: "3:4",  sharedBy: ["抖店视频封面", "小红书"] },
  { key: "9x16", ratio: "9:16", sharedBy: ["抖店视频封面"] },
  { key: "16x9", ratio: "16:9", sharedBy: ["淘宝视频封面"] },
];

export function MasterGallery({ images }: { images: SourceImage[] }) {
  return (
    <div>
      <div className="text-xs uppercase opacity-50 mb-2">Master 资产 (5/原图 × {images.length} 原图)</div>
      <div className="grid grid-cols-5 gap-2">
        {MASTER_RATIOS.map((m) => (
          <div key={m.key} className="bg-zinc-900 border border-zinc-700 rounded p-2">
            <div className="aspect-square bg-gradient-to-br from-amber-200 to-amber-800 rounded mb-2 flex items-center justify-center text-xs font-bold">
              {m.ratio}
            </div>
            <div className="text-xs font-semibold">{m.key}</div>
            <div className="text-[10px] opacity-55 mt-1">共用：{m.sharedBy.slice(0,2).join("、")}{m.sharedBy.length > 2 ? "+" : ""}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
