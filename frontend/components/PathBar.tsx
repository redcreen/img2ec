"use client";
import { api } from "@/lib/api";

export function PathBar({
  path, label = "目录", compact = false,
}: { path: string; label?: string; compact?: boolean }) {
  const onReveal = () => api.reveal(path);
  const onCopy = () => navigator.clipboard?.writeText(path);

  if (compact) {
    // 与状态/按钮同行的紧凑形态：截断长路径，单击在 Finder 打开
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] opacity-80 min-w-0">
        <span className="opacity-55 flex-shrink-0">📂</span>
        <code
          className="font-mono bg-zinc-950 px-1.5 py-0.5 rounded text-zinc-400 max-w-[360px] truncate cursor-pointer hover:text-zinc-200"
          onClick={onReveal}
          title={`${path}/  ← 单击在 Finder 中显示`}
        >{path}/</code>
        <button
          onClick={onCopy}
          className="text-zinc-500 hover:text-zinc-200 flex-shrink-0"
          title="复制路径"
        >📋</button>
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2 flex-wrap text-xs">
      <span className="opacity-55">📂 {label}：</span>
      <code className="font-mono bg-zinc-950 px-2 py-0.5 rounded text-zinc-400">{path}/</code>
      <button onClick={onReveal} className="px-2 py-0.5 border border-zinc-700 rounded text-[11px] hover:text-zinc-100">在 Finder 中显示</button>
      <button onClick={onCopy} className="px-2 py-0.5 border border-zinc-700 rounded text-[11px] hover:text-zinc-100">复制路径</button>
    </div>
  );
}
