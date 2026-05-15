"use client";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";
import type { SceneMode, ReferenceImage } from "@/lib/genConfig";
import { appendPrompt, getPresets } from "@/lib/promptPresets";
import { useToast } from "@/lib/useToast";
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
  pid, sid, vid, scene,
  extraPrompt, extraWeight, onExtraPromptChange, onExtraWeightChange,
  extraNegativePrompt = "", onExtraNegativePromptChange,
  mode, onModeChange,
  referenceImage, onReferenceChange,
  onSceneChanged,
}: {
  pid: string; sid: string; vid?: string; scene?: Scene;
  extraPrompt: string;
  extraWeight: number;
  onExtraPromptChange: (s: string) => void;
  onExtraWeightChange: (w: number) => void;
  extraNegativePrompt?: string;
  onExtraNegativePromptChange?: (s: string) => void;
  mode: SceneMode;
  onModeChange: (m: SceneMode) => void;
  referenceImage: ReferenceImage | null;
  onReferenceChange: (r: ReferenceImage | null) => void;
  onSceneChanged?: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [activeRatio, setActiveRatio] = useState<string>("1x1");
  const [coverLightbox, setCoverLightbox] = useState(false);
  const [pickModal, setPickModal] = useState(false);
  const [picking, setPicking] = useState(false);
  const [uploadingRef, setUploadingRef] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const disableScene = mode === "reference";
  const hasReference = mode === "reference" && referenceImage !== null;
  const swrKey = open
    ? `prompt-${sid}-${vid ?? ""}-${extraWeight}-${extraPrompt}-${extraNegativePrompt}-${mode}-${hasReference}`
    : null;
  const { data, error } = useSWR(
    swrKey,
    () => api.previewPrompt(
      pid, sid, extraPrompt, extraWeight, extraNegativePrompt,
      disableScene, hasReference, vid,
    ),
  );

  const pickRefFile = async (f: File | null) => {
    if (!f) return;
    setUploadingRef(true);
    try {
      const r = await api.uploadReferenceImage(pid, f);
      onReferenceChange({ path: r.path, url: r.url, name: r.name });
    } catch (e: any) {
      toast.error("参考图上传失败：" + e.message);
    } finally {
      setUploadingRef(false);
    }
  };

  // 选了"参考图" tab 时支持 ⌘V/Ctrl+V 直接粘贴
  useEffect(() => {
    if (mode !== "reference") return;
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const it of Array.from(items)) {
        if (it.kind === "file" && it.type.startsWith("image/")) {
          const f = it.getAsFile();
          if (f) { e.preventDefault(); pickRefFile(f); return; }
        }
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [mode, pid]);

  return (
    <div>
      {/* 选项卡：模板 / 参考图 / 都不选 */}
      <div className="flex gap-1 mb-3">
        <TabBtn active={mode === "template"} onClick={() => onModeChange("template")}>📋 模板</TabBtn>
        <TabBtn active={mode === "reference"} onClick={() => onModeChange("reference")}>🖼 参考图</TabBtn>
        <TabBtn active={mode === "none"} onClick={() => onModeChange("none")}>🚫 都不选</TabBtn>
      </div>

      {/* === 模板 tab === */}
      {mode === "template" && (
        <div className="flex items-start gap-3 mb-3">
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
            <button
              onClick={() => setPickModal(true)}
              disabled={picking}
              className="text-[10px] px-2 py-0.5 rounded bg-blue-600/15 hover:bg-blue-600/30 border border-blue-500/50 hover:border-blue-400 text-blue-200 transition disabled:opacity-50 mb-1"
              title={scene ? "选其他模板" : "选一个模板"}
            >{scene ? "⮂ 更换模板" : "📋 选择模板"}</button>
            {scene ? (
              <div>
                <div className="text-xs font-semibold">{scene.name}</div>
                <div className="text-[10px] opacity-55 mt-0.5 line-clamp-2">{scene.category}</div>
                <div className="text-[10px] opacity-55 mt-0.5 line-clamp-2">{scene.desc || scene.prompt.slice(0, 60)}</div>
              </div>
            ) : (
              <div className="text-xs opacity-60">未设置模板 — 点上方按钮选一个</div>
            )}
          </div>
        </div>
      )}

      {/* === 都不选 tab === */}
      {mode === "none" && (
        <div className="mb-3 text-xs opacity-70 bg-zinc-950 border border-zinc-700 rounded p-3">
          🚫 本次生成不用 SKU 模板，也不用参考图 —— 完全由下方"附加提示词"驱动。
        </div>
      )}

      {/* === 参考图 tab === */}
      {mode === "reference" && (
        <div className="mb-3">
          {referenceImage ? (
            <div className="flex items-start gap-3">
              <img
                src={referenceImage.url}
                alt={referenceImage.name}
                className="w-32 h-32 rounded object-cover border border-zinc-700 flex-shrink-0"
              />
              <div className="flex-1 text-xs min-w-0">
                <div className="opacity-80 mb-1 truncate" title={referenceImage.name}>{referenceImage.name}</div>
                <div className="opacity-50 mb-2 text-[10px]">参考图驱动 · 本次生成会忽略 SKU 模板</div>
                <div className="flex gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingRef}
                    className="text-[11px] underline opacity-60 hover:opacity-100 disabled:opacity-30"
                  >换一张</button>
                  <button
                    onClick={() => onReferenceChange(null)}
                    className="text-[11px] underline opacity-60 hover:opacity-100"
                  >移除</button>
                </div>
              </div>
            </div>
          ) : (
            <label
              className="block border-2 border-dashed border-zinc-700 rounded p-4 text-center cursor-pointer hover:border-blue-500 transition"
              onDrop={(e) => { e.preventDefault(); pickRefFile(e.dataTransfer.files?.[0] || null); }}
              onDragOver={(e) => e.preventDefault()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => pickRefFile(e.target.files?.[0] || null)}
              />
              <div className="text-sm">{uploadingRef ? "上传中…" : "点击选择 · 拖入 · 或 ⌘V/Ctrl+V 粘贴"}</div>
              <div className="text-[10px] opacity-50 mt-1">参考图作为场景指引；模型把产品换到类似场景里</div>
            </label>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => pickRefFile(e.target.files?.[0] || null)}
          />
        </div>
      )}

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
              if (vid) {
                await api.patchVariant(pid, sid, vid, { scene_id: sceneId });
              } else {
                await api.patchSku(pid, sid, { scene_id: sceneId });
              }
              onSceneChanged?.();
            } finally { setPicking(false); }
          }}
        />
      )}

      {/* 附加提示词（正向） — 任一 mode 下都可用 */}
      <div className="mb-2 bg-zinc-950 border border-zinc-700 rounded p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-[11px] uppercase tracking-wide opacity-70">
            <span className="text-green-400 mr-1">✚</span>附加提示词 · 正向
          </div>
          <div className="text-[10px] opacity-50">不持久化 · 只影响本次生成</div>
        </div>
        {/* 一键插入模板 */}
        <div className="flex flex-wrap gap-1">
          {getPresets(mode).filter(p => p.kind === "positive").map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => onExtraPromptChange(appendPrompt(extraPrompt, p.text))}
              className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 hover:border-green-500 hover:text-green-200 transition"
              title={p.text}
            >+ {p.label}</button>
          ))}
        </div>
        <textarea
          value={extraPrompt}
          onChange={(e) => onExtraPromptChange(e.target.value)}
          placeholder={
            mode === "reference"
              ? "例：产品放在画面中央偏下，占 40% 大小；沿用参考图的暖色调；产品颜色与图案严格保持原图；不要复制参考图里的文字"
              : "例：保留产品 logo 不被遮挡；产品摆放在桌面靠近窗户的位置；偏暖光"
          }
          rows={3}
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

      {/* 附加提示词（负向）—— 独立卡片让它一眼可见 */}
      {onExtraNegativePromptChange && (
        <div className="mb-3 bg-zinc-950 border border-zinc-700 rounded p-3 space-y-2">
          <div className="text-[11px] uppercase tracking-wide opacity-70">
            <span className="text-red-400 mr-1">⊘</span>附加提示词 · 负向（绝对不要出现）
          </div>
          {/* 负向预设 */}
          {getPresets(mode).filter(p => p.kind === "negative").map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => onExtraNegativePromptChange(appendPrompt(extraNegativePrompt, p.text))}
              className="text-[10px] px-2 py-0.5 mr-1 rounded bg-zinc-800 border border-zinc-700 hover:border-red-500 hover:text-red-200 transition"
              title={p.text}
            >+ {p.label}</button>
          ))}
          <textarea
            value={extraNegativePrompt}
            onChange={(e) => onExtraNegativePromptChange(e.target.value)}
            placeholder="例：不要出现 logo、文字、水印、其他产品、人、手、动物、塑料感"
            rows={2}
            className="w-full text-xs bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 resize-y font-mono"
          />
        </div>
      )}

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
              {(data.scene_name || data.scene_prompt) ? (
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
              ) : hasReference ? (
                <div className="text-[11px] opacity-60">参考图驱动模式 · 模板不参与；prompt 让模型对齐参考图的构图/光影。</div>
              ) : (
                <div className="text-[11px] opacity-60">已禁用模板 · 完整 prompt 仅由"附加提示词"组成。</div>
              )}

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

function TabBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1.5 rounded border transition ${
        active
          ? "bg-blue-600 text-white border-blue-500"
          : "bg-zinc-950 text-zinc-300 border-zinc-700 hover:border-zinc-500"
      }`}
    >{children}</button>
  );
}
