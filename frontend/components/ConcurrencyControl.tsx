"use client";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useToast } from "@/lib/useToast";

/** 并发数控件（顶栏，停止按钮前）。
 *  - 显示 Celery worker pool 当前大小
 *  - – / + 调整（1–16），即时 pool_grow / pool_shrink
 */
export function ConcurrencyControl() {
  const toast = useToast();
  const { data, mutate } = useSWR("concurrency", () => api.getConcurrency(), {
    refreshInterval: 8000,
  });
  const [busy, setBusy] = useState(false);
  const [optimistic, setOptimistic] = useState<number | null>(null);
  const min = data?.min ?? 1;
  const max = data?.max ?? 16;
  const display = optimistic ?? data?.current ?? null;

  useEffect(() => {
    if (optimistic !== null && data?.current === optimistic) setOptimistic(null);
  }, [data, optimistic]);

  const change = async (delta: number) => {
    if (busy || display === null) return;
    const next = Math.max(min, Math.min(max, display + delta));
    if (next === display) return;
    setBusy(true); setOptimistic(next);
    try {
      await api.setConcurrency(next);
      await mutate();
    } catch (e: any) {
      toast.error("调整并发失败：" + e.message);
      setOptimistic(null);
    } finally {
      setBusy(false);
    }
  };

  if (display === null) {
    return <span className="text-[10px] opacity-50">并发: …</span>;
  }
  return (
    <div className="inline-flex items-center gap-1 px-2 py-1 rounded border border-zinc-700 bg-zinc-900 text-[11px]" title="生图并发数：同时跑几张图。改完立即生效。">
      <span className="opacity-60">并发</span>
      <button
        onClick={() => change(-1)}
        disabled={busy || display <= min}
        className="w-5 h-5 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 leading-none"
      >−</button>
      <span className="w-5 text-center font-semibold tabular-nums">{display}</span>
      <button
        onClick={() => change(1)}
        disabled={busy || display >= max}
        className="w-5 h-5 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 leading-none"
      >+</button>
    </div>
  );
}
