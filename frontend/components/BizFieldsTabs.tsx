"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { PlatformCopy } from "@/lib/types";

const PLATFORM_LABEL: Record<string, string> = {
  douyin: "抖店", shipinhao: "视频号", xiaohongshu: "小红书",
};

const TITLE_LIMIT: Record<string, number> = {
  douyin: 60, shipinhao: 30, xiaohongshu: 20,
};

function copyToClipboard(text: string) {
  navigator.clipboard?.writeText(text);
}

function FieldRow({ label, value, limit }: { label: string; value: string; limit?: number }) {
  const overLimit = limit !== undefined && value.length > limit;
  return (
    <div className="mb-3">
      <div className="flex items-center text-[10px] uppercase opacity-60 mb-1">
        <span>{label}</span>
        {limit !== undefined && (
          <span className={`ml-2 ${overLimit ? "text-red-400" : ""}`}>
            {value.length}/{limit}
          </span>
        )}
        <button
          onClick={() => copyToClipboard(value)}
          className="ml-auto text-[10px] underline hover:text-white"
        >复制</button>
      </div>
      <div className={`text-sm bg-zinc-950 border ${overLimit ? "border-red-700" : "border-zinc-700"} rounded px-3 py-2 break-words`}>
        {value || <span className="opacity-40 italic">(empty)</span>}
      </div>
    </div>
  );
}

function ListField({ label, items }: { label: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="mb-3">
      <div className="flex items-center text-[10px] uppercase opacity-60 mb-1">
        <span>{label}</span>
        <span className="ml-2">{items.length} 项</span>
        <button
          onClick={() => copyToClipboard(items.join("\n"))}
          className="ml-auto text-[10px] underline hover:text-white"
        >复制全部</button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span key={i} className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs">{it}</span>
        ))}
      </div>
    </div>
  );
}

export function BizFieldsTabs({ skuId }: { skuId: string }) {
  const { data, mutate, isLoading } = useSWR(`copy-${skuId}`, () => api.listCopy(skuId));
  const [active, setActive] = useState<string>("douyin");
  const [regenerating, setRegenerating] = useState(false);

  const copy = data?.find(c => c.platform === active);
  const platforms = ["douyin", "shipinhao", "xiaohongshu"] as const;

  const onRegen = async () => {
    setRegenerating(true);
    try {
      await api.regenerateCopy(skuId);
      await mutate();
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="mt-6 bg-zinc-900 border border-zinc-700 rounded p-4">
      <div className="flex items-center mb-4 gap-2">
        <h3 className="text-sm font-semibold flex-1">商品文案（3 平台）</h3>
        <button
          onClick={onRegen}
          disabled={regenerating}
          className="text-xs bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded font-semibold disabled:opacity-50"
        >{regenerating ? "重新生成中…" : "重新生成"}</button>
      </div>

      <div className="flex gap-1 mb-4">
        {platforms.map(p => (
          <button
            key={p}
            onClick={() => setActive(p)}
            className={`text-xs px-3 py-1.5 rounded ${active === p ? "bg-blue-600 text-white" : "opacity-60 hover:opacity-100"}`}
          >{PLATFORM_LABEL[p]}</button>
        ))}
      </div>

      {isLoading && <p className="text-xs opacity-60">加载中…</p>}
      {!isLoading && !copy && (
        <p className="text-xs opacity-60">暂无文案。处理完图后会自动生成；或点击"重新生成"。</p>
      )}
      {copy && (
        <div>
          <FieldRow label={active === "xiaohongshu" ? "笔记标题" : "标题"} value={copy.title} limit={TITLE_LIMIT[active]} />
          {copy.subtitle && <FieldRow label="副标题" value={copy.subtitle} />}
          <ListField label="卖点" items={copy.selling_points} />
          {copy.description_md && (
            <FieldRow label={active === "xiaohongshu" ? "笔记正文" : "详情段落"} value={copy.description_md} />
          )}
          {copy.category_path && <FieldRow label="推荐类目" value={copy.category_path} />}
          {copy.keywords?.length > 0 && <ListField label="关键词" items={copy.keywords} />}
          {copy.hashtags?.length > 0 && <ListField label="Hashtags" items={copy.hashtags} />}
        </div>
      )}
    </div>
  );
}
