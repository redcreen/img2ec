"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SKU, Variant } from "@/lib/types";
import { useToast } from "@/lib/useToast";

const STYLES = [
  { key: "white", label: "白底尺寸图" },
  { key: "template", label: "模板尺寸图" },
] as const;
type StyleKey = (typeof STYLES)[number]["key"];

export function DimensionPanel({
  pid, sid, sku, variant, onChanged,
}: {
  pid: string; sid: string; sku: SKU; variant: Variant;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [length, setLength] = useState<string>(sku.length_cm?.toString() ?? "");
  const [width, setWidth] = useState<string>(sku.width_cm?.toString() ?? "");
  const [height, setHeight] = useState<string>(sku.height_cm?.toString() ?? "");
  const [selected, setSelected] = useState<Set<StyleKey>>(() => new Set(["white"]));
  const [busy, setBusy] = useState<"saving" | "submitting" | null>(null);

  const parseDim = (s: string): number | null => {
    const t = s.trim();
    if (!t) return null;
    const v = parseFloat(t);
    return isNaN(v) || v <= 0 ? null : v;
  };

  const allFilled =
    parseDim(length) !== null && parseDim(width) !== null && parseDim(height) !== null;
  const dirty =
    parseDim(length) !== sku.length_cm ||
    parseDim(width) !== sku.width_cm ||
    parseDim(height) !== sku.height_cm;
  const states = variant.dimension_states ?? {};
  const generatingStyles = (Object.keys(states) as StyleKey[]).filter(
    (s) => states[s]?.status === "generating"
  );
  const anyGenerating = generatingStyles.length > 0;

  const toggleStyle = (k: StyleKey) => {
    if (busy || states[k]?.status === "generating") return;
    const next = new Set(selected);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    setSelected(next);
  };

  const onSave = async () => {
    setBusy("saving");
    try {
      await api.updateDimensions(pid, sid, {
        length_cm: parseDim(length),
        width_cm: parseDim(width),
        height_cm: parseDim(height),
      });
      onChanged();
    } catch (e: any) {
      toast.error("保存失败：" + e.message);
    } finally {
      setBusy(null);
    }
  };

  const onGenerate = async () => {
    if (!allFilled) {
      toast.warn("三项尺寸都需要填写");
      return;
    }
    if (selected.size === 0) {
      toast.warn("请至少勾选一种尺寸图风格");
      return;
    }
    if (dirty) {
      try {
        await api.updateDimensions(pid, sid, {
          length_cm: parseDim(length),
          width_cm: parseDim(width),
          height_cm: parseDim(height),
        });
      } catch (e: any) {
        toast.error("保存失败：" + e.message);
        return;
      }
    }
    setBusy("submitting");
    try {
      await api.regenerateDimension(pid, sid, Array.from(selected), variant.id);
      onChanged();
    } catch (e: any) {
      toast.error("提交失败：" + e.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="text-[11px] opacity-70 mb-2">尺寸图（可选）</div>
      <div className="flex flex-wrap items-end gap-2 mb-2">
        <Field label="长 (cm)" value={length} onChange={setLength} />
        <Field label="宽 (cm)" value={width} onChange={setWidth} />
        <Field label="高 (cm)" value={height} onChange={setHeight} />
        {dirty && !anyGenerating && (
          <button
            onClick={onSave}
            disabled={busy !== null}
            className="px-3 py-1.5 text-xs border border-zinc-600 rounded hover:bg-zinc-800 disabled:opacity-40"
          >
            {busy === "saving" ? "保存中…" : "保存"}
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-2">
        {STYLES.map((s) => {
          const isSelected = selected.has(s.key);
          const st = states[s.key]?.status ?? "idle";
          const exists = !!variant.dimension_urls?.[s.key];
          const isGen = st === "generating";
          return (
            <label
              key={s.key}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[11px] cursor-pointer ${
                isGen
                  ? "bg-amber-900/30 text-amber-200 border border-amber-700"
                  : isSelected
                  ? "bg-blue-600/30 text-blue-200 border border-blue-500"
                  : "bg-zinc-800 text-zinc-300 border border-zinc-700"
              }`}
              onClick={() => toggleStyle(s.key)}
            >
              <span>{isGen ? "↻" : isSelected ? "☑" : "☐"}</span>
              <span>{s.label}</span>
              {exists && !isGen && <span className="opacity-60 ml-1">已生成</span>}
              {isGen && <span className="opacity-80 ml-1">生成中…</span>}
            </label>
          );
        })}
        <button
          onClick={onGenerate}
          disabled={!allFilled || busy !== null || anyGenerating || selected.size === 0}
          className="px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 rounded font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {busy === "submitting"
            ? "提交中…"
            : anyGenerating
            ? `Codex 生成中…(${generatingStyles.length})`
            : `▶ 生成尺寸图（${selected.size}）`}
        </button>
        {anyGenerating && <span className="text-[11px] opacity-60">~50s/张，后台运行</span>}
      </div>

      {/* 错误信息 */}
      {STYLES.map((s) => {
        const st = states[s.key];
        if (st?.status !== "error") return null;
        return (
          <p key={s.key} className="text-xs text-red-400 mb-1">
            {s.label} 生成失败：{st.err}
          </p>
        );
      })}

      {/* 加入主图/详情图请到下方"图片库"面板中操作（统一管理所有图） */}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col text-[10px] opacity-70">
      {label}
      <input
        type="number"
        step="0.1"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-20 mt-0.5 px-2 py-1 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-100"
        placeholder="-"
      />
    </label>
  );
}
