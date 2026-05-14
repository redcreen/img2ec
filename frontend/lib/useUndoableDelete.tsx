"use client";
/** 可撤销删除：点 × 立即从 UI 隐藏，10s 内可撤销；超时才真删。
 *  - enqueue(id, label, doDelete, onCancel?)
 *  - isPending(id): 让消费者过滤掉已"删除"的卡片
 *  - 用户在 10s 内点撤销 → onCancel？？ 顶多刷新 UI，文件本就没动
 *  - 用户离开页面 → useEffect cleanup 把未撤销的全部 flush 删除（best-effort）
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";

export interface PendingDelete {
  id: string;            // 唯一 key：建议 path 或 path:resource
  label: string;         // 展示用："原图1 · 1:1"
  doDelete: () => Promise<void>;
  onCancel?: () => void;
  expiresAt: number;
}

interface UndoCtx {
  pending: PendingDelete[];
  isPending: (id: string) => boolean;
  enqueue: (entry: Omit<PendingDelete, "expiresAt">) => void;
  cancel: (id: string) => void;
}

const Ctx = createContext<UndoCtx | null>(null);

const TTL_MS = 10_000;

export function UndoProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingDelete[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  // pendingRef 让 cleanup 拿到最新的 pending 列表
  const pendingRef = useRef<PendingDelete[]>([]);
  pendingRef.current = pending;

  const enqueue = useCallback((e: Omit<PendingDelete, "expiresAt">) => {
    // 同 id 重复入队 → 先 cancel timer，再覆盖
    const prevTimer = timers.current.get(e.id);
    if (prevTimer) clearTimeout(prevTimer);

    const expiresAt = Date.now() + TTL_MS;
    const entry: PendingDelete = { ...e, expiresAt };
    setPending((p) => [...p.filter((x) => x.id !== e.id), entry]);

    const t = setTimeout(async () => {
      try {
        await e.doDelete();
      } catch (err) {
        console.error("[useUndoableDelete] flush failed:", err);
      } finally {
        timers.current.delete(e.id);
        setPending((p) => p.filter((x) => x.id !== e.id));
      }
    }, TTL_MS);
    timers.current.set(e.id, t);
  }, []);

  const cancel = useCallback((id: string) => {
    const t = timers.current.get(id);
    if (t) clearTimeout(t);
    timers.current.delete(id);
    setPending((p) => {
      const entry = p.find((x) => x.id === id);
      try { entry?.onCancel?.(); } catch (err) { console.error(err); }
      return p.filter((x) => x.id !== id);
    });
  }, []);

  const isPending = useCallback(
    (id: string) => pending.some((x) => x.id === id),
    [pending],
  );

  // 卸载时把所有未到期的删除全部 flush（best-effort，不 await）
  useEffect(() => {
    return () => {
      pendingRef.current.forEach((entry) => {
        const t = timers.current.get(entry.id);
        if (t) clearTimeout(t);
        entry.doDelete().catch((err) =>
          console.error("[useUndoableDelete] unmount flush failed:", err),
        );
      });
      timers.current.clear();
    };
  }, []);

  const value = useMemo(
    () => ({ pending, isPending, enqueue, cancel }),
    [pending, isPending, enqueue, cancel],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <UndoToast pending={pending} cancel={cancel} />
    </Ctx.Provider>
  );
}

export function useUndo(): UndoCtx {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error("useUndo must be used within <UndoProvider>");
  }
  return ctx;
}

// ----- Toast -----

function UndoToast({
  pending, cancel,
}: { pending: PendingDelete[]; cancel: (id: string) => void }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (pending.length === 0) return;
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, [pending.length]);

  if (pending.length === 0) return null;
  const last = pending[pending.length - 1];
  const remainMs = Math.max(0, last.expiresAt - now);
  const remain = Math.ceil(remainMs / 1000);
  const extra = pending.length - 1;
  const totalMs = 10_000;
  const pct = Math.max(0, Math.min(100, (remainMs / totalMs) * 100));

  return (
    <div
      key={last.id}
      role="alert"
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] bg-zinc-900 border-2 border-red-500/70 rounded-xl shadow-2xl shadow-red-900/40 px-4 py-3 flex items-center gap-3 text-sm min-w-[420px] max-w-[90vw] animate-[undo-pop_0.18s_ease-out]"
    >
      <span className="text-2xl">🗑</span>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold truncate">已删除 {last.label}</div>
        <div className="text-[11px] opacity-70">
          {remain} 秒内可撤销
          {extra > 0 && <span className="opacity-70"> · 队列还有 {extra} 项</span>}
        </div>
        {/* 倒计时进度条 */}
        <div className="h-1 bg-zinc-800 rounded mt-1.5 overflow-hidden">
          <div
            className="h-full bg-red-500 transition-[width] duration-200 ease-linear"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <button
        onClick={() => cancel(last.id)}
        className="text-sm px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold whitespace-nowrap"
      >↶ 撤销</button>
      <style jsx>{`
        @keyframes undo-pop {
          from { opacity: 0; transform: translate(-50%, 20px); }
          to   { opacity: 1; transform: translate(-50%, 0); }
        }
      `}</style>
    </div>
  );
}
