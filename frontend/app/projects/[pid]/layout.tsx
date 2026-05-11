"use client";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { pid } = useParams<{ pid: string }>();
  const path = usePathname();
  const { data: project } = useSWR(pid ? `project-${pid}` : null,
    () => api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const isSku = path?.includes("/skus");
  const isScene = path?.includes("/scenes");

  return (
    <main className="max-w-[1600px] mx-auto p-4">
      <header className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 mb-3">
        <h1 className="text-lg font-bold">img2ec</h1>
        <span className="text-xs opacity-60">
          <Link href="/projects" className="text-blue-400 hover:underline">项目</Link>
          {project && <> / <strong className="text-zinc-100">{project.name}</strong></>}
        </span>
        <div className="flex-1" />
        <Link href={`/projects/${pid}/skus`}
          className={`px-3 py-1.5 text-xs rounded ${isSku ? "bg-blue-600 text-white" : "opacity-60 hover:opacity-100"}`}>SKU</Link>
        <Link href={`/projects/${pid}/scenes`}
          className={`px-3 py-1.5 text-xs rounded ${isScene ? "bg-blue-600 text-white" : "opacity-60 hover:opacity-100"}`}>模板库</Link>
      </header>
      {children}
    </main>
  );
}
