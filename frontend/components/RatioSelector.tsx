"use client";
import { useMemo, useState } from "react";

const ALL_RATIOS = ["1x1", "long", "3x4", "9x16", "16x9"] as const;
const LABEL: Record<string, string> = {
  "1x1": "1:1 主图",
  "long": "long 长图详情页",
  "3x4": "3:4 竖版封面",
  "9x16": "9:16 短视频封面",
  "16x9": "16:9 横版封面",
};

export function RatioSelector({
  existingRatios,
  busy,
  onTrigger,
}: {
  existingRatios: string[];
  busy: boolean;
  onTrigger: (ratios: string[]) => void;
}) {
  const existingSet = useMemo(() => new Set(existingRatios), [existingRatios]);
  const [selected, setSelected] = useState<Set<string>>(() => {
    // 默认勾选未生成的 ratio
    return new Set(ALL_RATIOS.filter(r => !existingSet.has(r)));
  });

  const toggle = (r: string) => {
    if (busy) return;
    if (existingSet.has(r)) return;  // 已生成的不让勾选（避免重生）
    const next = new Set(selected);
    if (next.has(r)) next.delete(r);
    else next.add(r);
    setSelected(next);
  };

  const selectedToGen = ALL_RATIOS.filter(r => selected.has(r) && !existingSet.has(r));
  const isInitialRun = existingRatios.length === 0;

  return (
    <div className="mt-3 pt-3 border-t border-zinc-800">
      <div className="text-[11px] opacity-70 mb-2">
        生成尺寸（已生成 {existingRatios.length}/5）
      </div>
      <div className="flex flex-wrap gap-2 mb-3">
        {ALL_RATIOS.map(r => {
          const isExisting = existingSet.has(r);
          const isSelected = selected.has(r);
          return (
            <label
              key={r}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[11px] cursor-pointer
                ${isExisting ? "bg-green-900/30 text-green-300 border border-green-700 cursor-default"
                  : isSelected ? "bg-blue-600/30 text-blue-200 border border-blue-500"
                  : "bg-zinc-800 text-zinc-400 border border-zinc-700"}`}
              onClick={() => toggle(r)}
            >
              {isExisting ? "✓" : isSelected ? "☑" : "☐"}
              <span>{LABEL[r]}</span>
              {isExisting && <span className="opacity-60 ml-1">已生成</span>}
            </label>
          );
        })}
      </div>
      <button
        disabled={busy || selectedToGen.length === 0}
        onClick={() => onTrigger(selectedToGen)}
        className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 rounded font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {busy ? "处理中…"
          : selectedToGen.length === 0 ? "请勾选要生成的尺寸"
          : isInitialRun ? `▶ 开始生成（${selectedToGen.length} 张）`
          : `▶ 继续生成（${selectedToGen.length} 张）`}
      </button>
    </div>
  );
}
