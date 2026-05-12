"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { FESTIVALS, type AIPreview } from "@/lib/types";

const STYLES = ["古风", "新中式", "国潮", "民俗手作"];

/** AI 关键词扩展（fire-and-forget）：填关键词 → 立即创建占位 scene → 模态关闭，
 *  列表里出现"⏳ AI 生成中"卡片，~90s 后自动填充。 */
export function AIKeywordsModal({
  pid, onClose, onSaved,
}: { pid: string; onClose: () => void; onSaved: () => void }) {
  const [keywords, setKeywords] = useState<string[]>([""]);
  const [festival, setFestival] = useState<string>("通用");
  const [style, setStyle] = useState<string>("新中式");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const filledKeywords = keywords.map(k => k.trim()).filter(Boolean);

  const run = async () => {
    if (filledKeywords.length === 0) { setErr("至少填一个关键词"); return; }
    setBusy(true); setErr(null);
    try {
      await api.aiQueueKeywords(pid, { keywords: filledKeywords, festival, style });
      onSaved();  // 关闭 modal + 触发 SWR 拉新列表
    } catch (e: any) {
      setErr(e.message || "启动失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Backdrop onClose={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-[560px] max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-sm font-semibold">🪄 AI 关键词扩展</h3>
          <button onClick={onClose} className="opacity-60 hover:opacity-100">✕</button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-[11px] opacity-70 block mb-1">关键词（1-8 个，中文，越具体越好）</label>
            <div className="space-y-1.5">
              {keywords.map((k, i) => (
                <div key={i} className="flex gap-1.5">
                  <input
                    value={k}
                    onChange={(e) => {
                      const next = [...keywords]; next[i] = e.target.value; setKeywords(next);
                    }}
                    placeholder={i === 0 ? "如：八仙桌" : i === 1 ? "如：暖窗光" : i === 2 ? "如：艾草菖蒲" : ""}
                    className="flex-1 px-2 py-1.5 text-sm bg-zinc-950 border border-zinc-700 rounded"
                  />
                  {keywords.length > 1 && (
                    <button
                      onClick={() => setKeywords(keywords.filter((_, j) => j !== i))}
                      className="px-2 text-zinc-500 hover:text-red-400"
                    >×</button>
                  )}
                </div>
              ))}
              {keywords.length < 8 && (
                <button
                  onClick={() => setKeywords([...keywords, ""])}
                  className="text-[11px] opacity-60 hover:opacity-100"
                >+ 加一个关键词</button>
              )}
            </div>
          </div>

          <div>
            <label className="text-[11px] opacity-70 block mb-1">节庆</label>
            <div className="flex flex-wrap gap-1.5">
              {FESTIVALS.map(f => (
                <Chip key={f} label={f} active={festival === f} onClick={() => setFestival(f)} />
              ))}
            </div>
          </div>

          <div>
            <label className="text-[11px] opacity-70 block mb-1">风格调性</label>
            <div className="flex gap-1.5">
              {STYLES.map(s => (
                <Chip key={s} label={s} active={style === s} onClick={() => setStyle(s)} />
              ))}
            </div>
          </div>

          <p className="text-[10px] opacity-50">
            点 ▶ 生成后会立即在列表里出现"⏳ AI 生成中"占位卡片，~1-2 分钟后自动填充完整 prompt + cover。
          </p>
        </div>

        {err && <p className="text-xs text-red-400 mt-3">{err}</p>}

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-3 py-1.5 text-sm border border-zinc-700 rounded">取消</button>
          <button
            onClick={run}
            disabled={busy || filledKeywords.length === 0}
            className="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-500 rounded font-semibold disabled:opacity-50"
          >{busy ? "提交中…" : "▶ 加入列表（后台生成）"}</button>
        </div>
      </div>
    </Backdrop>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-2 py-1 rounded border transition ${
        active ? "bg-blue-600 text-white border-blue-500"
               : "bg-zinc-950 text-zinc-300 border-zinc-700 hover:border-zinc-500"
      }`}
    >{label}</button>
  );
}

// 保留：AIReferenceModal 现在仍在用旧的"预览-保存"模式
export function Preview({
  preview, busy, err, onRetry, onSave, onClose,
}: {
  preview: AIPreview; busy: boolean; err: string | null;
  onRetry: () => void; onSave: () => void; onClose: () => void;
}) {
  return (
    <>
      <div className="flex gap-3 mb-3">
        <img src={preview.cover_url} alt="" className="w-40 h-40 rounded object-cover bg-zinc-800 flex-shrink-0" />
        <div className="flex-1 text-sm min-w-0">
          <div className="text-base font-semibold mb-1">{preview.name}</div>
          <div className="text-[11px] opacity-70 mb-2">{preview.desc}</div>
          <div className="text-[10px] opacity-50">节庆: {preview.festival}</div>
        </div>
      </div>
      <details className="text-[11px] mb-3 bg-zinc-950 border border-zinc-700 rounded p-2 max-h-32 overflow-y-auto">
        <summary className="cursor-pointer opacity-70 mb-1">完整英文 prompt</summary>
        <pre className="whitespace-pre-wrap font-mono opacity-80 mt-1">{preview.prompt}</pre>
      </details>
      {err && <p className="text-xs text-red-400 mb-2">{err}</p>}
      <div className="flex justify-end gap-2">
        <button onClick={onClose} disabled={busy} className="px-3 py-1.5 text-sm border border-zinc-700 rounded disabled:opacity-50">取消</button>
        <button onClick={onRetry} disabled={busy} className="px-3 py-1.5 text-sm border border-zinc-700 rounded disabled:opacity-50">重新生成</button>
        <button onClick={onSave} disabled={busy} className="px-3 py-1.5 text-sm bg-green-600 hover:bg-green-500 rounded font-semibold disabled:opacity-50">
          {busy ? "保存中…" : "✓ 保存为模板"}
        </button>
      </div>
    </>
  );
}

function Backdrop({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      {children}
    </div>
  );
}
