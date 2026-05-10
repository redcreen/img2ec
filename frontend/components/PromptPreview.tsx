"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

const RATIO_ORDER = ["1x1", "long", "3x4", "9x16", "16x9"] as const;
const RATIO_LABEL: Record<string, string> = {
  "1x1": "1:1 主图",
  "long": "long 长图",
  "3x4": "3:4 竖版",
  "9x16": "9:16 短视频",
  "16x9": "16:9 横版",
};

export function PromptPreview({ pid, sid }: { pid: string; sid: string }) {
  const [open, setOpen] = useState(false);
  const [activeRatio, setActiveRatio] = useState<string>("1x1");
  const { data, error } = useSWR(
    open ? `prompt-${sid}` : null,
    () => api.previewPrompt(pid, sid)
  );

  return (
    <div className="mt-3 pt-3 border-t border-zinc-800">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-[11px] opacity-70 hover:opacity-100 flex items-center gap-1"
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>查看完整 Prompt（送给 Codex 的实际指令）</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {error && <p className="text-xs text-red-400">加载失败：{String(error)}</p>}
          {!data && !error && <p className="text-xs opacity-50">加载中…</p>}
          {data && (
            <>
              <div className="bg-zinc-950 border border-zinc-700 rounded p-3 text-[11px]">
                <div className="opacity-50 uppercase text-[10px] mb-1">场景模板</div>
                <div className="font-semibold mb-1">{data.scene_name}</div>
                <div className="opacity-80">{data.scene_prompt}</div>
                {data.negative_prompt && (
                  <>
                    <div className="opacity-50 uppercase text-[10px] mt-2 mb-1">负面 prompt</div>
                    <div className="opacity-70">{data.negative_prompt}</div>
                  </>
                )}
              </div>

              <div>
                <div className="text-[10px] opacity-50 uppercase mb-1.5">完整 prompt（按 ratio 切换）</div>
                <div className="flex gap-1 mb-2">
                  {RATIO_ORDER.map(r => (
                    <button
                      key={r}
                      onClick={() => setActiveRatio(r)}
                      className={`text-[10px] px-2 py-1 rounded ${activeRatio === r ? "bg-blue-600 text-white" : "bg-zinc-800 opacity-70 hover:opacity-100"}`}
                    >{RATIO_LABEL[r]}</button>
                  ))}
                </div>
                <pre className="bg-zinc-950 border border-zinc-700 rounded p-3 text-[11px] whitespace-pre-wrap leading-relaxed font-mono max-h-[40vh] overflow-y-auto">
                  {data.per_ratio[activeRatio]}
                </pre>
                <button
                  onClick={() => navigator.clipboard?.writeText(data.per_ratio[activeRatio])}
                  className="mt-1 text-[10px] underline opacity-60 hover:opacity-100"
                >复制此 prompt</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
