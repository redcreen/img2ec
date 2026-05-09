import Link from "next/link";
import type { SKU } from "@/lib/types";
import { StatusPill } from "./StatusPill";

export function SkuRow({ sku, sceneName }: { sku: SKU; sceneName: string }) {
  const total = sku.images.length;
  const done = sku.images.filter(i => i.status === "done").length;
  const meta =
    sku.status === "running" ? `${done}/${total} 已完成` :
    sku.status === "done" ? `${total * 4} 张输出（4 平台）` :
    sku.status === "error" ? `${done}/${total} 成功，可重试` :
    `${total} 张原图 / 场景：${sceneName}`;

  return (
    <Link href={`/projects/${sku.project_id}/skus/${sku.id}`}
      className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-3 mb-2 flex items-center gap-3 cursor-pointer transition">
      <div className="w-14 h-14 bg-gradient-to-br from-zinc-700 to-zinc-900 rounded flex items-center justify-center text-xs opacity-60">
        {total} 图
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold mb-1">{sku.name}</div>
        <div className="text-xs opacity-60 flex gap-2 items-center">
          <StatusPill status={sku.status} />
          <span>{meta}</span>
        </div>
      </div>
    </Link>
  );
}
