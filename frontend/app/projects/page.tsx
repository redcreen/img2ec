"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { NewProjectModal } from "@/components/NewProjectModal";

export default function ProjectsPage() {
  const { data, mutate, isLoading } = useSWR("projects", () => api.listProjects());
  const [showModal, setShowModal] = useState(false);

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
        {data?.map(p => (
          <Link key={p.id} href={`/projects/${p.id}/skus`}
            className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-4 transition">
            <div className="h-20 bg-gradient-to-br from-zinc-700 to-zinc-900 rounded mb-3 flex items-center justify-center text-3xl opacity-50">📁</div>
            <h3 className="text-sm font-semibold mb-1">{p.name}</h3>
            <p className="text-xs opacity-60">{p.desc || "（无说明）"}</p>
            <p className="text-xs opacity-60 mt-1">{p.sku_count} SKU · {p.scene_count} 模板</p>
          </Link>
        ))}
      </div>

      {showModal && <NewProjectModal onClose={() => setShowModal(false)}
        onCreated={() => { setShowModal(false); mutate(); }} />}
    </main>
  );
}
