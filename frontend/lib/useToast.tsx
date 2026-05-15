"use client";
/** 通用非阻塞 toast：替代 window.alert，支持 info / warn / error / success
 *  四级；自动消失（error 6s，其它 4s），点击关闭；多条堆叠在底部居中。
 *
 *  用法：
 *      const t = useToast();
 *      t.error("删除失败：...");
 *      t.info("已保存");
 *
 *  根 layout 需要包 <ToastProvider> 才能用 useToast。 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";

type Level = "info" | "warn" | "error" | "success";

interface ToastEntry {
  id: string;
  level: Level;
  text: string;
  expiresAt: number;
}

interface ToastApi {
  info: (text: string) => void;
  warn: (text: string) => void;
  error: (text: string) => void;
  success: (text: string) => void;
  show: (level: Level, text: string) => void;
}

const Ctx = createContext<ToastApi | null>(null);

const TTL: Record<Level, number> = { info: 4000, success: 4000, warn: 5000, error: 6000 };

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    const t = timers.current.get(id);
    if (t) clearTimeout(t);
    timers.current.delete(id);
    setItems((xs) => xs.filter((x) => x.id !== id));
  }, []);

  const show = useCallback((level: Level, text: string) => {
    const id = Math.random().toString(36).slice(2, 10);
    const ttl = TTL[level];
    const entry: ToastEntry = { id, level, text, expiresAt: Date.now() + ttl };
    setItems((xs) => [...xs, entry]);
    const t = setTimeout(() => dismiss(id), ttl);
    timers.current.set(id, t);
  }, [dismiss]);

  // 卸载时清干净（避免 setState on unmounted）
  useEffect(() => () => { timers.current.forEach((t) => clearTimeout(t)); timers.current.clear(); }, []);

  const api = useMemo<ToastApi>(() => ({
    info:   (t) => show("info", t),
    warn:   (t) => show("warn", t),
    error:  (t) => show("error", t),
    success:(t) => show("success", t),
    show,
  }), [show]);

  return (
    <Ctx.Provider value={api}>
      {children}
      <ToastStack items={items} dismiss={dismiss} />
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

// ---------- 渲染 ----------

const LEVEL_STYLE: Record<Level, string> = {
  info:    "border-zinc-600 bg-zinc-900 text-zinc-100",
  success: "border-emerald-600 bg-emerald-950/90 text-emerald-100",
  warn:    "border-amber-500 bg-amber-950/90 text-amber-100",
  error:   "border-red-500 bg-red-950/90 text-red-100",
};
const LEVEL_ICON: Record<Level, string> = {
  info: "ℹ️", success: "✓", warn: "⚠", error: "✕",
};

function ToastStack({
  items, dismiss,
}: { items: ToastEntry[]; dismiss: (id: string) => void }) {
  if (items.length === 0) return null;
  return (
    <div
      className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[90] flex flex-col gap-2 items-center pointer-events-none"
      aria-live="polite"
    >
      {items.map((t) => (
        <div
          key={t.id}
          role="status"
          onClick={() => dismiss(t.id)}
          className={`pointer-events-auto cursor-pointer border-2 rounded-lg shadow-lg px-4 py-2.5 flex items-center gap-3 text-sm max-w-[640px] animate-[toast-pop_0.18s_ease-out] ${LEVEL_STYLE[t.level]}`}
          title="点击关闭"
        >
          <span className="text-base flex-shrink-0">{LEVEL_ICON[t.level]}</span>
          <span className="whitespace-pre-wrap break-words">{t.text}</span>
        </div>
      ))}
      <style jsx>{`
        @keyframes toast-pop {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
