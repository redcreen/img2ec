"use client";
import { useEffect, useMemo, useState } from "react";

const RATIO_KEYS = ["1x1", "long", "3x4", "9x16", "16x9"] as const;
const CLOSEUP_KEYS = ["front", "side", "detail"] as const;
const DIM_KEYS = ["dim_white", "dim_template"] as const;
const ALL_KEYS = [...RATIO_KEYS, ...CLOSEUP_KEYS, ...DIM_KEYS] as const;

const LABEL: Record<string, string> = {
  "1x1": "1:1 主图",
  "long": "long 长图详情页",
  "3x4": "3:4 竖版封面",
  "9x16": "9:16 短视频封面",
  "16x9": "16:9 横版封面",
  "front":  "特写 · 正面",
  "side":   "特写 · 侧面",
  "detail": "特写 · 部位细节",
  "dim_white": "尺寸图 · 白底",
  "dim_template": "尺寸图 · 模板",
};
const GROUP: Record<string, "ratio" | "closeup" | "dim"> = {
  "1x1": "ratio", "long": "ratio", "3x4": "ratio", "9x16": "ratio", "16x9": "ratio",
  "front": "closeup", "side": "closeup", "detail": "closeup",
  "dim_white": "dim", "dim_template": "dim",
};

interface Dims {
  length: string;
  width: string;
  height: string;
}

export function RatioSelector({
  existingRatios,
  existingDimStyles,
  initialDimensions,
  sourceImages,
  busy,
  onTrigger,
}: {
  existingRatios: string[];
  existingDimStyles: string[];
  initialDimensions: { length_cm: number | null; width_cm: number | null; height_cm: number | null };
  sourceImages: Array<{ id: string; name: string; src_url: string | null }>;
  busy: boolean;
  onTrigger: (args: {
    ratios: string[];
    dimStyles: string[];
    dimImageIndices: number[];
    dims: { length: number | null; width: number | null; height: number | null };
  }) => void;
}) {
  // 已生成 set：master ratio + dim_<style>
  const existingSet = useMemo(() => {
    const s = new Set<string>(existingRatios);
    for (const st of existingDimStyles) s.add(`dim_${st}`);
    return s;
  }, [existingRatios, existingDimStyles]);

  const [selected, setSelected] = useState<Set<string>>(() => {
    // 默认勾选未生成的比例图（5 项）；特写 + 尺寸图按需勾
    return new Set(ALL_KEYS.filter((r) => !existingSet.has(r) && GROUP[r] === "ratio"));
  });

  const [dims, setDims] = useState<Dims>(() => ({
    length: initialDimensions.length_cm?.toString() ?? "",
    width: initialDimensions.width_cm?.toString() ?? "",
    height: initialDimensions.height_cm?.toString() ?? "",
  }));
  // 选择哪些原图作为尺寸图的 source（多选）；默认勾第 0 张
  const [dimImageIndices, setDimImageIndices] = useState<Set<number>>(new Set([0]));
  // 当 SKU 的 dimensions 从外部更新（保存后刷新），同步进来
  useEffect(() => {
    setDims({
      length: initialDimensions.length_cm?.toString() ?? "",
      width: initialDimensions.width_cm?.toString() ?? "",
      height: initialDimensions.height_cm?.toString() ?? "",
    });
  }, [initialDimensions.length_cm, initialDimensions.width_cm, initialDimensions.height_cm]);

  const toggle = (r: string) => {
    if (busy) return;
    const next = new Set(selected);
    if (next.has(r)) next.delete(r);
    else next.add(r);
    setSelected(next);
  };

  const selectedList = ALL_KEYS.filter((r) => selected.has(r));
  const selectedRatios = selectedList.filter((r) => GROUP[r] !== "dim");
  const selectedDimStyles = selectedList
    .filter((r) => GROUP[r] === "dim")
    .map((r) => r.replace("dim_", ""));
  const willRegen = selectedList.filter((r) => existingSet.has(r));
  const willCreate = selectedList.filter((r) => !existingSet.has(r));

  const parseDim = (s: string): number | null => {
    const t = s.trim();
    if (!t) return null;
    const v = parseFloat(t);
    return isNaN(v) || v <= 0 ? null : v;
  };
  const parsedDims = {
    length: parseDim(dims.length),
    width: parseDim(dims.width),
    height: parseDim(dims.height),
  };
  const dimsAllFilled = parsedDims.length !== null && parsedDims.width !== null && parsedDims.height !== null;
  const wantDim = selectedDimStyles.length > 0;
  const dimError = wantDim && !dimsAllFilled;

  const buttonLabel = (() => {
    if (busy) return "处理中…";
    if (selectedList.length === 0) return "请勾选要生成的规格";
    if (dimError) return "尺寸图需要填长×宽×高";
    if (willRegen.length > 0 && willCreate.length === 0) return `▶ 重新生成（${willRegen.length} 张，覆盖原图）`;
    if (willRegen.length > 0) return `▶ 生成 ${willCreate.length} 张 + 重生 ${willRegen.length} 张`;
    return `▶ 生成（${willCreate.length} 张）`;
  })();

  const onClick = () => {
    if (dimError) return;
    if (willRegen.length > 0) {
      const ok = confirm(
        `要覆盖以下已生成的规格吗？\n${willRegen.map((r) => LABEL[r]).join("、")}\n\n旧图会被新图替换。`
      );
      if (!ok) return;
    }
    onTrigger({
      ratios: selectedRatios,
      dimStyles: selectedDimStyles,
      dimImageIndices: Array.from(dimImageIndices).sort((a, b) => a - b),
      dims: parsedDims,
    });
  };

  return (
    <div>
      <div className="text-[11px] opacity-70 mb-2">
        生成规格（已生成 {existingSet.size}/{ALL_KEYS.length}）— 点击已生成的可重生
      </div>
      <div className="text-[10px] opacity-50 mb-1">比例图（带场景）</div>
      <ChipGroup
        keys={RATIO_KEYS as readonly string[]}
        existingSet={existingSet}
        selected={selected}
        toggle={toggle}
      />
      <div className="text-[10px] opacity-50 mt-2 mb-1">特写图（白底，多角度）</div>
      <ChipGroup
        keys={CLOSEUP_KEYS as readonly string[]}
        existingSet={existingSet}
        selected={selected}
        toggle={toggle}
      />
      <div className="text-[10px] opacity-50 mt-2 mb-1">尺寸图（含规格标注）</div>
      <ChipGroup
        keys={DIM_KEYS as readonly string[]}
        existingSet={existingSet}
        selected={selected}
        toggle={toggle}
      />

      {/* 尺寸输入 + 源原图选择（任意 dim 被勾时显示） */}
      {wantDim && (
        <div className="mt-2 bg-zinc-950 border border-zinc-800 rounded p-2 space-y-2">
          <div className="flex items-end gap-2 flex-wrap">
            <DimInput label="长 (cm)" value={dims.length} onChange={(v) => setDims({ ...dims, length: v })} />
            <DimInput label="宽 (cm)" value={dims.width} onChange={(v) => setDims({ ...dims, width: v })} />
            <DimInput label="高 (cm)" value={dims.height} onChange={(v) => setDims({ ...dims, height: v })} />
            {dimError && <span className="text-[10px] text-red-400">三项尺寸都需填写</span>}
          </div>
          {sourceImages.length > 0 && (
            <div>
              <div className="text-[10px] opacity-60 mb-1">基于哪些原图生成（可多选）</div>
              <div className="flex flex-wrap gap-1.5">
                {sourceImages.map((img, idx) => {
                  const isSelected = dimImageIndices.has(idx);
                  return (
                    <label
                      key={img.id}
                      className={`flex items-center gap-1.5 px-2 py-1 rounded border cursor-pointer text-[10px] ${
                        isSelected
                          ? "bg-blue-600/30 text-blue-200 border-blue-500"
                          : "bg-zinc-800 text-zinc-400 border-zinc-700"
                      }`}
                      onClick={() => {
                        const next = new Set(dimImageIndices);
                        if (next.has(idx)) next.delete(idx);
                        else next.add(idx);
                        if (next.size > 0) setDimImageIndices(next);
                      }}
                    >
                      {img.src_url && (
                        <img src={img.src_url} alt="" className="w-5 h-5 object-cover rounded" />
                      )}
                      <span>原图 {idx + 1}</span>
                    </label>
                  );
                })}
              </div>
              <div className="text-[10px] opacity-50 mt-0.5">
                共生成 {selectedDimStyles.length * dimImageIndices.size} 张尺寸图
                （{selectedDimStyles.length} 风格 × {dimImageIndices.size} 原图）
              </div>
            </div>
          )}
        </div>
      )}

      <button
        disabled={busy || selectedList.length === 0 || dimError}
        onClick={onClick}
        className="mt-3 px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 rounded font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {buttonLabel}
      </button>
    </div>
  );
}

function DimInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col text-[10px] opacity-70">
      {label}
      <input
        type="number"
        step="0.1"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-16 mt-0.5 px-2 py-1 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-100"
        placeholder="-"
      />
    </label>
  );
}

function ChipGroup({
  keys, existingSet, selected, toggle,
}: {
  keys: readonly string[];
  existingSet: Set<string>;
  selected: Set<string>;
  toggle: (r: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {keys.map((r) => {
        const isExisting = existingSet.has(r);
        const isSelected = selected.has(r);
        const cls = isExisting && !isSelected
          ? "bg-green-900/30 text-green-300 border border-green-700"
          : isExisting && isSelected
          ? "bg-amber-900/40 text-amber-200 border border-amber-500"
          : isSelected
          ? "bg-blue-600/30 text-blue-200 border border-blue-500"
          : "bg-zinc-800 text-zinc-400 border border-zinc-700";
        const icon = isExisting && !isSelected
          ? "✓"
          : isExisting && isSelected
          ? "↻"
          : isSelected
          ? "☑"
          : "☐";
        return (
          <label
            key={r}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[11px] cursor-pointer ${cls}`}
            onClick={() => toggle(r)}
          >
            <span>{icon}</span>
            <span>{LABEL[r]}</span>
            {isExisting && !isSelected && <span className="opacity-60 ml-1">已生成</span>}
            {isExisting && isSelected && <span className="opacity-80 ml-1">将重生</span>}
          </label>
        );
      })}
    </div>
  );
}
