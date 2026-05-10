import type { SKU } from "@/lib/types";
import { api } from "@/lib/api";

export function BatchDownloadButton({ pid, skus }: { pid: string; skus: SKU[] }) {
  const doneCount = skus.filter((s) => s.status === "done").length;
  if (doneCount === 0) return null;

  return (
    <a
      href={api.downloadProjectAll(pid)}
      className="px-3 py-2 text-sm bg-blue-600 hover:bg-blue-500 rounded font-semibold whitespace-nowrap"
    >
      ⬇ 下载已完成 ({doneCount})
    </a>
  );
}
