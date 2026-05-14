import Link from "next/link";
import type { SKU } from "@/lib/types";
import { StatusPill } from "./StatusPill";

const PREVIEW_RATIOS = ["1x1", "long", "3x4", "9x16"] as const;
const MAX_THUMBS = 4;

export function SkuRow({ sku, sceneName }: { sku: SKU; sceneName: string }) {
  const total = sku.images.length;
  const done = sku.images.filter(i => i.status === "done").length;
  const meta =
    sku.status === "running" ? `${done}/${total} 已完成` :
    sku.status === "done" ? `${total * 4} 张输出（4 平台）` :
    sku.status === "error" ? `${done}/${total} 成功，可重试` :
    `${total} 张原图 / 模板：${sceneName}`;

  const thumbs = pickThumbnails(sku);

  return (
    <Link href={`/projects/${sku.project_id}/skus/${sku.id}`}
      className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-3 mb-2 flex items-center gap-3 cursor-pointer transition">
      {/* 名字 */}
      <div className="text-sm font-semibold flex-shrink-0 min-w-[120px] max-w-[260px] truncate" title={sku.name}>
        {sku.name}
      </div>
      {/* 紧跟着名字的缩略图组 */}
      {thumbs.length > 0 ? (
        <div className="flex gap-1 flex-shrink-0">
          {thumbs.map((t, i) => (
            <img
              key={i}
              src={t.url}
              alt={t.label}
              title={t.label}
              className="w-12 h-12 rounded object-cover bg-zinc-800 border border-zinc-700"
              loading="lazy"
            />
          ))}
        </div>
      ) : (
        <div className="w-12 h-12 bg-gradient-to-br from-zinc-700 to-zinc-900 rounded flex items-center justify-center text-[10px] opacity-60 flex-shrink-0">
          {total} 图
        </div>
      )}
      {/* 元信息 */}
      <div className="flex-1 min-w-0 text-xs opacity-60 flex gap-2 items-center">
        <StatusPill status={sku.status} />
        <span className="truncate">{meta}</span>
      </div>
    </Link>
  );
}

interface Thumb { url: string; label: string }

function pickThumbnails(sku: SKU): Thumb[] {
  const out: Thumb[] = [];
  const seen = new Set<string>();
  for (const v of sku.variants ?? []) {
    for (const img of v.images ?? []) {
      const masters = img.master_urls ?? {};
      for (const r of PREVIEW_RATIOS) {
        const u = masters[r];
        if (u && !seen.has(u)) {
          out.push({ url: u, label: `${v.color_name} · ${img.name} · ${r}` });
          seen.add(u);
          if (out.length >= MAX_THUMBS) return out;
          break;
        }
      }
      if (out.length >= MAX_THUMBS) return out;
      if (Object.keys(masters).length === 0 && img.src_url && !seen.has(img.src_url)) {
        out.push({ url: img.src_url, label: `${v.color_name} · ${img.name}（原图）` });
        seen.add(img.src_url);
        if (out.length >= MAX_THUMBS) return out;
      }
    }
  }
  return out;
}
