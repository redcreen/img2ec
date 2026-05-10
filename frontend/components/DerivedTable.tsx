import type { SourceImage } from "@/lib/types";

const DERIVED_TABLE: Record<string, Array<{ name: string; from: string; size: string }>> = {
  "抖店": [
    { name: "main",       from: "1x1",  size: "1080×1080" },
    { name: "detail-750", from: "long", size: "750×∞" },
    { name: "cover-3x4",  from: "3x4",  size: "900×1200" },
    { name: "cover-9x16", from: "9x16", size: "1080×1920" },
  ],
  "视频号": [
    { name: "main",       from: "1x1",  size: "800×800" },
    { name: "detail-750", from: "long", size: "750×∞" },
    { name: "cover-1x1",  from: "1x1",  size: "800×800" },
    { name: "cover-3x4",  from: "3x4",  size: "900×1200" },
  ],
  "淘宝": [
    { name: "main",       from: "1x1",  size: "800×800" },
    { name: "detail-750", from: "long", size: "750×∞" },
    { name: "cover-16x9", from: "16x9", size: "1920×1080" },
    { name: "cover-1x1",  from: "1x1",  size: "800×800" },
  ],
  "小红书": [
    { name: "note-1x1",   from: "1x1",  size: "1080×1080" },
    { name: "note-3x4",   from: "3x4",  size: "900×1200" },
    { name: "long",       from: "long", size: "750×∞" },
  ],
};

export function DerivedTable({ images }: { images: SourceImage[] }) {
  const total = Object.values(DERIVED_TABLE).reduce((sum, arr) => sum + arr.length, 0) * images.length;
  return (
    <div>
      <div className="text-xs uppercase opacity-50 mb-2">平台派生输出（共 {total} 张）</div>
      {Object.entries(DERIVED_TABLE).map(([platform, items]) => (
        <div key={platform} className="bg-zinc-900 border border-zinc-700 rounded p-3 mb-2">
          <div className="text-xs font-semibold mb-2">{platform}（{items.length}/原图 × {images.length} = {items.length * images.length}）</div>
          {items.map((it) => (
            <div key={it.name} className="flex gap-2 text-[11px] mb-1">
              <span className="px-1.5 py-0.5 bg-zinc-950 border border-zinc-700 rounded text-[10px] font-semibold">{it.from}</span>
              <span className="opacity-40">→</span>
              <span className="flex-1">{it.name}</span>
              <span className="opacity-55">{it.size}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
