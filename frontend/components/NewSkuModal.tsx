"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";
import { Lightbox } from "./Lightbox";

interface PickedFile {
  id: string;       // 稳定 id（避免 React key 冲突 / 拖拽后顺序错位）
  file: File;
  url: string;      // objectURL
}

let _idSeq = 0;
function nextId() { return `f${Date.now()}-${++_idSeq}`; }

export function NewSkuModal({
  pid, scenes, onClose, onCreated,
}: { pid: string; scenes: Scene[]; onClose: () => void; onCreated: (sid: string) => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [picks, setPicks] = useState<PickedFile[]>([]);
  const [sceneId, setSceneId] = useState(scenes[0]?.id ?? "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // 卸载时统一回收所有 objectURL
  useEffect(() => {
    return () => {
      // 用最新闭包的 picks 不够稳；统一在 removeFile / addFiles 时按需 revoke
      // 这里只做兜底
    };
  }, []);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming || incoming.length === 0) return;
    const added: PickedFile[] = Array.from(incoming).map((f) => ({
      id: nextId(),
      file: f,
      url: URL.createObjectURL(f),
    }));
    setPicks((prev) => [...prev, ...added]);
  };

  const openPicker = () => {
    // 重要：先清空 value，否则相同文件再选不会触发 onChange（浏览器特性）
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
      fileInputRef.current.click();
    }
  };

  const removeFile = (id: string) => {
    setPicks((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target) URL.revokeObjectURL(target.url);
      return prev.filter((p) => p.id !== id);
    });
  };

  const reorderFile = (from: number, to: number) => {
    if (from === to) return;
    setPicks((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };

  const submit = async () => {
    if (!name.trim()) return setErr("SKU 名必填");
    if (!sceneId) return setErr("请选模板");
    if (picks.length === 0) return setErr("请选至少一张原图");
    setBusy(true);
    setErr("");
    try {
      const sku = await api.createSku(pid, { name: name.trim(), scene_id: sceneId });
      for (let i = 0; i < picks.length; i++) {
        try {
          await api.uploadImage(pid, sku.id, picks[i].file);
        } catch (e: any) {
          throw new Error(`第 ${i + 1} 张原图上传失败：${e.message}`);
        }
      }
      // 释放 objectURL
      picks.forEach((p) => URL.revokeObjectURL(p.url));
      onCreated(sku.id);
      onClose();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  // 项目里没有任何模板时，先引导去建模板
  if (scenes.length === 0) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[440px] max-w-[600px]" onClick={e => e.stopPropagation()}>
          <h2 className="text-lg font-bold mb-3">先去模板库建一个模板</h2>
          <p className="text-sm opacity-75 mb-4">
            创建 SKU 需要选一个模板（决定 Codex 生图的场景风格 — 白底/中式木桌等）。
            当前项目还没有模板，先去模板库建一个或导入默认模板。
          </p>
          <div className="flex gap-2 justify-end">
            <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
            <button
              onClick={() => { onClose(); router.push(`/projects/${pid}/scenes`); }}
              className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold"
            >去模板库</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-full max-w-[780px] max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold mb-4">新建 SKU</h2>

        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">SKU 名</label>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm"
            placeholder="例如：蓝色保温杯 500ml"
            autoFocus
          />
        </div>

        {/* 原图（多选 + 拖拽排序 + 缩略预览 + 点击放大） */}
        <div className="mb-4">
          <label className="text-xs opacity-65 block mb-1">
            原图（可多张 · 拖拽调整顺序 · 点缩略放大 · × 移除）
          </label>
          <div className="flex flex-wrap gap-2 bg-zinc-950 border border-zinc-800 rounded p-2 min-h-[88px]">
            {picks.map((p, i) => (
              <div
                key={p.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "move";
                  e.dataTransfer.setData("text/plain", String(i));
                  setDragFrom(i);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  setDragOver(i);
                }}
                onDragLeave={() => setDragOver((c) => (c === i ? null : c))}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(null);
                  setDragFrom(null);
                  const from = parseInt(e.dataTransfer.getData("text/plain"));
                  if (!isNaN(from)) reorderFile(from, i);
                }}
                onDragEnd={() => { setDragFrom(null); setDragOver(null); }}
                className={`relative w-20 group cursor-grab active:cursor-grabbing rounded overflow-hidden border-2 transition ${
                  dragOver === i && dragFrom !== null && dragFrom !== i
                    ? "border-amber-400 ring-2 ring-amber-400/40"
                    : "border-zinc-700"
                } ${dragFrom === i ? "opacity-40" : ""}`}
                title="拖拽调整顺序"
              >
                <div className="aspect-square bg-zinc-800 relative">
                  <img
                    src={p.url}
                    alt={p.file.name}
                    className="w-full h-full object-cover cursor-zoom-in"
                    onClick={() => setLightboxUrl(p.url)}
                  />
                  <span className="absolute top-0 left-0 bg-black/70 text-white text-[9px] px-1 leading-[14px]">
                    {i + 1}
                  </span>
                </div>
                <div
                  className="text-[9px] truncate px-1 py-0.5 bg-zinc-900 opacity-80"
                  title={p.file.name}
                >{p.file.name}</div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); removeFile(p.id); }}
                  className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-600 text-white text-[10px] leading-none opacity-0 group-hover:opacity-100 hover:bg-red-500"
                  title="移除"
                >×</button>
              </div>
            ))}
            <button
              type="button"
              onClick={openPicker}
              className="w-20 h-20 flex items-center justify-center border-2 border-dashed border-zinc-700 hover:border-blue-500 rounded text-[11px] opacity-70 hover:opacity-100"
            >+ 添加</button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => addFiles(e.target.files)}
              style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
            />
          </div>
          {picks.length > 0 && (
            <p className="text-[10px] opacity-50 mt-1">
              {picks.length} 张原图 · 第 1 张作为详情页 hero
            </p>
          )}
        </div>

        {/* 模板 — 卡片式选择，带代表图 */}
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">模板（场景风格）</label>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 max-h-[300px] overflow-y-auto bg-zinc-950 border border-zinc-800 rounded p-2">
            {scenes.map((sc) => {
              const active = sceneId === sc.id;
              return (
                <button
                  key={sc.id}
                  type="button"
                  onClick={() => setSceneId(sc.id)}
                  className={`text-left border-2 rounded overflow-hidden transition ${
                    active
                      ? "border-blue-500 ring-2 ring-blue-500/30"
                      : "border-zinc-700 hover:border-zinc-500 opacity-85 hover:opacity-100"
                  }`}
                  title={sc.desc || sc.prompt.slice(0, 80)}
                >
                  <div className="aspect-square bg-zinc-800 relative">
                    {sc.cover_url ? (
                      <img src={sc.cover_url} alt={sc.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[10px] opacity-40">无代表图</div>
                    )}
                    {active && (
                      <div className="absolute top-1 right-1 bg-blue-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold shadow">✓</div>
                    )}
                  </div>
                  <div className="p-1.5 bg-zinc-900">
                    <div className="text-[11px] font-semibold truncate">{sc.name}</div>
                    <div className="text-[10px] opacity-60 truncate">{sc.category}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button
            className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit}
            disabled={busy}
          >{busy ? "创建中…" : "创建并开始处理"}</button>
        </div>
      </div>

      {lightboxUrl && (
        <Lightbox src={lightboxUrl} alt="原图预览" onClose={() => setLightboxUrl(null)} />
      )}
    </div>
  );
}
