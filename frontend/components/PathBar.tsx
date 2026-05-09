"use client";
import { api } from "@/lib/api";

export function PathBar({ path, label = "目录" }: { path: string; label?: string }) {
  const onReveal = () => api.reveal(path);
  const onCopy = () => navigator.clipboard?.writeText(path);

  return (
    <div className="flex items-center gap-2 flex-wrap text-xs">
      <span className="opacity-55">📂 {label}：</span>
      <code className="font-mono bg-zinc-950 px-2 py-0.5 rounded text-zinc-400">{path}/</code>
      <button onClick={onReveal} className="px-2 py-0.5 border border-zinc-700 rounded text-[11px] hover:text-zinc-100">在 Finder 中显示</button>
      <button onClick={onCopy} className="px-2 py-0.5 border border-zinc-700 rounded text-[11px] hover:text-zinc-100">复制路径</button>
    </div>
  );
}
