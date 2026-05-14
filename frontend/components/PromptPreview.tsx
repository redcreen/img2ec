"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";
import { Lightbox } from "./Lightbox";
import { SceneSelectModal } from "./SceneSelectModal";

const RATIO_ORDER = ["1x1", "long", "3x4", "9x16", "16x9"] as const;
const RATIO_LABEL: Record<string, string> = {
  "1x1": "1:1 主图",
  "long": "long 长图",
  "3x4": "3:4 竖版",
  "9x16": "9:16 短视频",
  "16x9": "16:9 横版",
};

export function PromptPreview({
  pid, sid, scene,
  extraPrompt, extraWeight, onExtraPromptChange, onExtraWeightChange,
  onSceneChanged,
}: {
  pid: string; sid: string; scene?: Scene;
  extraPrompt: string;
  extraWeight: number;
  onExtraPromptChange: (s: string) => void;
  onExtraWeightChange: (w: number) => void;
  onSceneChanged?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [activeRatio, setActiveRatio] = useState<string>("1x1");
  const [coverLightbox, setCoverLightbox] = useState(false);
  const [pickModal, setPickModal] = useState(false);
  const [picking, setPicking] = useState(false);
  // 重新拉 prompt：让用户调 extra 后立刻能在「完整 prompt」里看到合成结果
  const swrKey = open ? `prompt-${sid}-${extraWeight}-${extraPrompt}` : null;
  const { data, error } = useSWR(
    swrKey,
    () => api.previewPrompt(pid, sid, extraPrompt, extraWeight)
  );

  return (
    <div>
      {/* 模板信息 inline 展示（折叠态也可见，点缩略图放大） */}
      <div className="flex items-start gap-3 mb-2">
        {scene?.cover_url && (
          <img
            src={scene.cover_url}
            alt={scene.name}
            onClick={() => setCoverLightbox(true)}
            className="w-20 h-20 rounded object-cover border border-zinc-700 flex-shrink-0 cursor-zoom-in hover:border-blue-500 transition"
            title="点击查看大图"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <div className="text-[10px] opacity-50 uppercase">模板</div>
            <button
              onClick={() => setPickModal(true)}
              disabled={picking}
              className="text-[10px] px-2 py-0.5 rounded bg-blue-600/15 hover:bg-blue-600/30 border border-blue-500/50 hover:border-blue-400 text-blue-200 transition disabled:opacity-50"
              title="更换 SKU 默认模板（生成时所有选中图都用这个）"
            >⮂ 更换模板</button>
          </div>
          {scene ? (
            <>
              <div className="text-xs font-semibold">{scene.name}</div>
              <div className="text-[10px] opacity-55 mt-0.5 line-clamp-2">{scene.category}</div>
              <div className="text-[10px] opacity-55 mt-0.5 line-clamp-2">{scene.desc || scene.prompt.slice(0, 60)}</div>
            </>
          ) : (
            <div className="text-xs opacity-60">未设置模板 — 点"⮂ 更换模板"选一个</div>
          )}
        </div>
      </div>

      {coverLightbox && scene?.cover_url && (
        <Lightbox src={scene.cover_url} alt={scene.name} onClose={() => setCoverLightbox(false)} />
      )}

      {pickModal && (
        <SceneSelectModal
          pid={pid}
          imageName="SKU 默认模板（生成时所有选中图都用这个）"
          currentSceneId={scene?.id ?? null}
          allowNull={false}
          onClose={() => setPickModal(false)}
          onPick={async (sceneId) => {
            if (!sceneId) return;
            setPicking(true);
            try {
              await api.patchSku(pid, sid, { scene_id: sceneId });
              onSceneChanged?.();
            } finally { setPicking(false); }
          }}
        />
      )}

      {/* 附加提示词（模板 prompt 下方） — 影响这次生成 */}
      <div className="mb-3 bg-zinc-950 border border-zinc-700 rounded p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-[10px] uppercase opacity-50">附加提示词（叠加在模板之上）</div>
          <div className="text-[10px] opacity-50">不持久化 · 只影响本次生成</div>
        </div>
        <textarea
          value={extraPrompt}
          onChange={(e) => onExtraPromptChange(e.target.value)}
          placeholder="例：保留产品 logo 不被遮挡；产品摆放在桌面靠近窗户的位置；偏暖光"
          rows={2}
          className="w-full text-xs bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 resize-y font-mono"
        />
        <div className="flex items-center gap-3">
          <span className="text-[10px] opacity-60 w-14">权重</span>
          <input
            type="range" min={0} max={1} step={0.05}
            value={extraWeight}
            onChange={(e) => onExtraWeightChange(parseFloat(e.target.value))}
            disabled={!extraPrompt.trim()}
            className="flex-1 accent-blue-500 disabled:opacity-40"
          />
          <input
            type="number" min={0} max={1} step={0.05}
            value={extraWeight}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v)) onExtraWeightChange(Math.min(1, Math.max(0, v)));
            }}
            disabled={!extraPrompt.trim()}
            className="w-16 text-xs bg-zinc-900 border border-zinc-700 rounded px-2 py-1 disabled:opacity-40 font-mono text-center"
          />
          <span className="text-[10px] opacity-50 w-32">
            {!extraPrompt.trim() ? "（先填提示词）"
              : extraWeight < 0.25 ? "轻度参考"
              : extraWeight < 0.55 ? "适度强调"
              : extraWeight < 0.85 ? "强烈强调"
                                   : "硬性约束"}
          </span>
        </div>
      </div>

      <button
        onClick={() => setOpen(o => !o)}
        className="text-[11px] opacity-70 hover:opacity-100 flex items-center gap-1"
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>查看完整 Prompt（模板 prompt + 送给 Codex 的实际指令）</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {error && <p className="text-xs text-red-400">加载失败：{String(error)}</p>}
          {!data && !error && <p className="text-xs opacity-50">加载中…</p>}
          {data && (
            <>
              <div className="bg-zinc-950 border border-zinc-700 rounded p-3 text-[11px]">
                <div className="opacity-50 uppercase text-[10px] mb-1">模板</div>
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
