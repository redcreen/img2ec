"use client";
import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { SceneCard } from "@/components/SceneCard";
import { SceneEditorModal } from "@/components/SceneEditorModal";
import { AIKeywordsModal } from "@/components/AIKeywordsModal";
import { AIReferenceModal } from "@/components/AIReferenceModal";
import { FESTIVALS, type Scene } from "@/lib/types";
import { useToast } from "@/lib/useToast";

export default function ScenesPage() {
  const { pid } = useParams<{ pid: string }>();
  const toast = useToast();
  // 当有「生成中」占位卡片时，自动轮询；否则不轮询
  const { data: scenes, mutate } = useSWR(
    pid ? `scenes-${pid}` : null,
    () => api.listScenes(pid),
    {
      refreshInterval: (data?: Scene[]) =>
        data && data.some(s => s.category.includes("生成中")) ? 3000 : 0,
    } as any,
  );
  const [editing, setEditing] = useState<Scene | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [batching, setBatching] = useState(false);
  const [aiKw, setAiKw] = useState(false);
  const [aiRef, setAiRef] = useState(false);
  const [festFilter, setFestFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");

  const onDeleteScene = async (sc: Scene) => {
    try {
      await api.deleteScene(pid, sc.id);
      await mutate();
    } catch (e: any) {
      toast.error("删除失败：" + e.message);
    }
  };

  const onBatch = async () => {
    if (!festFilter) return;
    if (!confirm(`将自动生成 10 个【${festFilter}】节庆模板，每张约 1-2 分钟（后台并发，整体约 5-10 分钟）。\n占位卡片会立即出现，生成完成后自动填充。\n继续？`)) return;
    setBatching(true);
    try {
      await api.aiBatchGenerate(pid, { festival: festFilter, count: 10 });
      await mutate();
    } catch (e: any) {
      toast.error("启动批量生成失败：" + e.message);
    } finally {
      setBatching(false);
    }
  };

  const onImport = async () => {
    setImporting(true);
    try {
      await api.importDefaultScenes(pid);
      await mutate();
    } catch (e: any) {
      toast.error("导入失败：" + e.message);
    } finally {
      setImporting(false);
    }
  };

  const filtered = useMemo(() => {
    if (!scenes) return [];
    return scenes.filter(sc => {
      if (festFilter && (sc.festival || "通用") !== festFilter) return false;
      if (sourceFilter) {
        const by = sc.created_by || "user";
        if (sourceFilter === "ai" && !by.startsWith("ai_")) return false;
        if (sourceFilter !== "ai" && by !== sourceFilter) return false;
      }
      return true;
    });
  }, [scenes, festFilter, sourceFilter]);

  // 按节庆给每个 chip 计数
  const festCounts = useMemo(() => {
    const m: Record<string, number> = {};
    (scenes || []).forEach(sc => {
      const k = sc.festival || "通用";
      m[k] = (m[k] || 0) + 1;
    });
    return m;
  }, [scenes]);

  return (
    <>
      <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[11px] opacity-60 mr-1">节庆:</span>
          <FilterChip label={`全部 (${scenes?.length || 0})`} active={!festFilter} onClick={() => setFestFilter("")} />
          {FESTIVALS.map(f => (
            <FilterChip
              key={f}
              label={`${f}${festCounts[f] ? ` (${festCounts[f]})` : ""}`}
              active={festFilter === f}
              onClick={() => setFestFilter(festFilter === f ? "" : f)}
            />
          ))}
          <span className="text-[11px] opacity-60 ml-3 mr-1">来源:</span>
          <FilterChip label="全部" active={!sourceFilter} onClick={() => setSourceFilter("")} />
          <FilterChip label="系统" active={sourceFilter === "system"} onClick={() => setSourceFilter(sourceFilter === "system" ? "" : "system")} />
          <FilterChip label="我的" active={sourceFilter === "user"} onClick={() => setSourceFilter(sourceFilter === "user" ? "" : "user")} />
          <FilterChip label="AI" active={sourceFilter === "ai"} onClick={() => setSourceFilter(sourceFilter === "ai" ? "" : "ai")} />
        </div>
        <div className="flex gap-2">
          {festFilter && (
            <button
              onClick={onBatch}
              disabled={batching}
              className="px-3 py-2 text-sm bg-amber-600 hover:bg-amber-500 rounded font-semibold disabled:opacity-50"
              title={`后台并发生成 10 个【${festFilter}】节庆模板，约 5-10 分钟`}
            >{batching ? "启动中…" : `🪄 自动生成 10 个${festFilter}模板`}</button>
          )}
          <button
            onClick={() => setAiKw(true)}
            className="px-3 py-2 text-sm bg-purple-600 hover:bg-purple-500 rounded font-semibold"
            title="给 AI 几个中文关键词，自动写完整 prompt + 生成 cover"
          >🪄 关键词 AI 生成</button>
          <button
            onClick={() => setAiRef(true)}
            className="px-3 py-2 text-sm bg-fuchsia-600 hover:bg-fuchsia-500 rounded font-semibold"
            title="上传一张参考图，AI 反推 prompt + 复现 cover"
          >🖼 从参考图反推</button>
          <button onClick={() => setCreating(true)}
            className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">+ 手工新建</button>
          <button
            onClick={onImport}
            disabled={importing}
            className="px-3 py-2 text-sm border border-zinc-700 rounded hover:border-blue-500 disabled:opacity-50"
          >{importing ? "导入中…" : "导入默认模板"}</button>
        </div>
      </div>
      {scenes && scenes.length === 0 && (
        <div className="opacity-60 text-center py-12">
          <p className="text-sm">还没模板。点「导入默认模板」一键加齐 20 个节庆向内置库（推荐），</p>
          <p className="text-xs mt-1">或用 AI 三秒造一个。</p>
        </div>
      )}
      {scenes && scenes.length > 0 && filtered.length === 0 && (
        <div className="opacity-60 text-center py-12 text-sm">该筛选下没有模板。</div>
      )}
      <div className="grid grid-cols-4 gap-3">
        {filtered.map(sc => (
          <SceneCard
            key={sc.id} scene={sc}
            onClick={() => setEditing(sc)}
            onDelete={() => onDeleteScene(sc)}
          />
        ))}
      </div>
      {(editing || creating) && (
        <SceneEditorModal pid={pid} scene={editing}
          onClose={() => { setEditing(null); setCreating(false); }}
          onSaved={() => { setEditing(null); setCreating(false); mutate(); }} />
      )}
      {aiKw && (
        <AIKeywordsModal pid={pid} onClose={() => setAiKw(false)} onSaved={() => { setAiKw(false); mutate(); }} />
      )}
      {aiRef && (
        <AIReferenceModal pid={pid} onClose={() => setAiRef(false)} onSaved={() => { setAiRef(false); mutate(); }} />
      )}
    </>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-2 py-1 rounded border transition ${
        active
          ? "bg-blue-600 text-white border-blue-500"
          : "bg-zinc-900 text-zinc-300 border-zinc-700 hover:border-zinc-500"
      }`}
    >{label}</button>
  );
}
