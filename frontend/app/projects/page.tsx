"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { NewProjectModal } from "@/components/NewProjectModal";
import type { Project } from "@/lib/types";
import { useToast } from "@/lib/useToast";

export default function ProjectsPage() {
  const { data, mutate, isLoading } = useSWR("projects", () => api.listProjects());
  const [showModal, setShowModal] = useState(false);
  const [renaming, setRenaming] = useState<Project | null>(null);

  return (
    <main className="max-w-6xl mx-auto p-4">
      <header className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 mb-3">
        <h1 className="text-lg font-bold">img2ec</h1>
        <span className="text-xs opacity-60">所有项目</span>
        <div className="flex-1" />
        <button onClick={() => setShowModal(true)}
          className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">+ 新建项目</button>
      </header>

      {isLoading && <p className="opacity-60">加载中…</p>}
      {data && data.length === 0 && (
        <div className="text-center py-12 opacity-60">还没有项目，点右上"新建项目"开始</div>
      )}
      <div className="grid grid-cols-3 gap-3">
        {data?.map((p) => (
          <ProjectCard
            key={p.id}
            p={p}
            onRename={() => setRenaming(p)}
            onDeleted={() => mutate()}
          />
        ))}
      </div>

      {showModal && <NewProjectModal onClose={() => setShowModal(false)}
        onCreated={() => { setShowModal(false); mutate(); }} />}
      {renaming && (
        <RenameProjectModal
          project={renaming}
          onClose={() => setRenaming(null)}
          onSaved={() => { setRenaming(null); mutate(); }}
        />
      )}
    </main>
  );
}

function ProjectCard({
  p, onRename, onDeleted,
}: { p: Project; onRename: () => void; onDeleted: () => void }) {
  const toast = useToast();
  const [deleting, setDeleting] = useState(false);
  const onDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(
      `确认删除项目「${p.name}」？\n\n会一起删掉：\n` +
      `· ${p.sku_count} 个 SKU 及其所有原图 / master / 派生 / 详情\n` +
      `· ${p.scene_count} 个模板\n` +
      `· 项目磁盘目录\n\n不可撤销。`,
    )) return;
    setDeleting(true);
    try {
      await api.deleteProject(p.id);
      onDeleted();
    } catch (err: any) {
      toast.error("删除失败：" + err.message);
    } finally {
      setDeleting(false);
    }
  };
  return (
    <div className="relative group">
      <Link href={`/projects/${p.id}/skus`}
        className="block bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-4 transition">
        <div className="h-20 bg-gradient-to-br from-zinc-700 to-zinc-900 rounded mb-3 flex items-center justify-center text-3xl opacity-50">📁</div>
        <h3 className="text-sm font-semibold mb-1">{p.name}</h3>
        <p className="text-xs opacity-60">{p.desc || "（无说明）"}</p>
        <p className="text-xs opacity-60 mt-1">{p.sku_count} SKU · {p.scene_count} 模板</p>
      </Link>
      {/* 右上角操作组 — hover 才出现 */}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onRename(); }}
          className="w-6 h-6 rounded bg-zinc-800/95 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs leading-none"
          title="改名 / 改描述"
        >✎</button>
        <button
          onClick={onDelete}
          disabled={deleting}
          className="w-6 h-6 rounded bg-red-700/85 hover:bg-red-600 text-white text-xs leading-none disabled:opacity-40"
          title="删除项目"
        >×</button>
      </div>
    </div>
  );
}

function RenameProjectModal({
  project, onClose, onSaved,
}: { project: Project; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(project.name);
  const [desc, setDesc] = useState(project.desc);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!name.trim()) return setErr("项目名必填");
    const trimmedName = name.trim();
    const trimmedDesc = desc.trim();
    const payload: { name?: string; desc?: string } = {};
    if (trimmedName !== project.name) payload.name = trimmedName;
    if (trimmedDesc !== project.desc) payload.desc = trimmedDesc;
    if (Object.keys(payload).length === 0) { onClose(); return; }
    setBusy(true);
    try {
      await api.patchProject(project.id, payload);
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[440px] max-w-[600px]" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">编辑项目</h2>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">项目名</label>
          <input value={name} onChange={e => setName(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm"
            autoFocus />
          <div className="text-[10px] opacity-50 mt-1">改名会重命名磁盘目录并同步所有子路径</div>
        </div>
        <div className="mb-4">
          <label className="text-xs opacity-65 block mb-1">说明</label>
          <textarea value={desc} onChange={e => setDesc(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" rows={2} />
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>
            {busy ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
