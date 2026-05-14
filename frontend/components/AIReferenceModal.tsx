"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FESTIVALS, type AIPreview } from "@/lib/types";
import { Preview } from "./AIKeywordsModal";

const STYLES = ["古风", "新中式", "国潮", "民俗手作"];

/** AI 参考图反推：上传一张好图 → Codex vision 分析 → 写 prompt → 复现 cover。 */
export function AIReferenceModal({
  pid, onClose, onSaved,
}: { pid: string; onClose: () => void; onSaved: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [festival, setFestival] = useState<string>("通用");
  const [style, setStyle] = useState<string>("新中式");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<AIPreview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const onPick = (f: File | null) => {
    if (filePreview) URL.revokeObjectURL(filePreview);
    setFile(f);
    setFilePreview(f ? URL.createObjectURL(f) : null);
  };

  // 支持 ⌘V / Ctrl+V 直接粘贴剪贴板里的图。Modal 打开期间监听 document
  // paste；preview 阶段（已经反推完，下一步是保存）不再接管粘贴。
  useEffect(() => {
    if (preview) return;
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const it of Array.from(items)) {
        if (it.kind === "file" && it.type.startsWith("image/")) {
          const f = it.getAsFile();
          if (f) {
            e.preventDefault();
            onPick(f);
            return;
          }
        }
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [preview, filePreview]);

  const runExpand = async () => {
    if (!file) { setErr("请先选择一张参考图"); return; }
    setBusy(true); setErr(null); setPreview(null);
    try {
      const p = await api.aiExpandReference(pid, file, festival, style);
      setPreview(p);
    } catch (e: any) {
      setErr(e.message || "生成失败");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!preview) return;
    setBusy(true); setErr(null);
    try {
      await api.createScene(pid, {
        name: preview.name,
        desc: preview.desc,
        category: `AI · ${preview.festival} · 反推`,
        prompt: preview.prompt,
        negative_prompt: preview.negative_prompt,
        festival: preview.festival,
        created_by: "ai_reference",
        cover_path: preview.cover_path,
      } as any);
      onSaved();
    } catch (e: any) {
      setErr("保存失败：" + e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div onClick={onClose} className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-[640px] max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-sm font-semibold">🖼 从参考图反推模板</h3>
          <button onClick={onClose} className="opacity-60 hover:opacity-100">✕</button>
        </div>

        {!preview ? (
          <>
            <div className="space-y-3">
              <div>
                <label className="text-[11px] opacity-70 block mb-1">参考图（同行作品 / Pinterest / 你看到的好图）</label>
                {filePreview ? (
                  <div className="flex items-start gap-3">
                    <img src={filePreview} alt="" className="w-40 h-40 rounded object-cover bg-zinc-800 border border-zinc-700" />
                    <div className="flex-1 text-xs">
                      <div className="opacity-80 mb-1 truncate">{file?.name}</div>
                      <div className="opacity-50 mb-2">{file ? `${(file.size / 1024).toFixed(0)} KB` : ""}</div>
                      <button
                        onClick={() => onPick(null)}
                        className="text-[11px] underline opacity-60 hover:opacity-100"
                      >换一张</button>
                    </div>
                  </div>
                ) : (
                  <label className="block border-2 border-dashed border-zinc-700 rounded p-6 text-center cursor-pointer hover:border-blue-500">
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => onPick(e.target.files?.[0] || null)}
                    />
                    <div className="text-sm">点击选择图片 · 或直接 ⌘V / Ctrl+V 粘贴</div>
                    <div className="text-[10px] opacity-50 mt-1">JPG / PNG / WebP，建议 1MB 以上质量好</div>
                  </label>
                )}
              </div>

              <div>
                <label className="text-[11px] opacity-70 block mb-1">节庆（如果反推后 AI 觉得不对会修正）</label>
                <div className="flex flex-wrap gap-1.5">
                  {FESTIVALS.map(f => (
                    <Chip key={f} label={f} active={festival === f} onClick={() => setFestival(f)} />
                  ))}
                </div>
              </div>

              <div>
                <label className="text-[11px] opacity-70 block mb-1">风格提示</label>
                <div className="flex gap-1.5">
                  {STYLES.map(s => (
                    <Chip key={s} label={s} active={style === s} onClick={() => setStyle(s)} />
                  ))}
                </div>
              </div>
            </div>

            {err && <p className="text-xs text-red-400 mt-3">{err}</p>}

            <div className="flex justify-end gap-2 mt-5">
              <button onClick={onClose} className="px-3 py-1.5 text-sm border border-zinc-700 rounded">取消</button>
              <button
                onClick={runExpand}
                disabled={busy || !file}
                className="px-3 py-1.5 text-sm bg-fuchsia-600 hover:bg-fuchsia-500 rounded font-semibold disabled:opacity-50"
              >{busy ? "分析中…（~90s）" : "▶ 反推 + 预览"}</button>
            </div>
          </>
        ) : (
          <Preview preview={preview} busy={busy} err={err}
                   onRetry={() => setPreview(null)}
                   onSave={save}
                   onClose={onClose} />
        )}
      </div>
    </div>
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
