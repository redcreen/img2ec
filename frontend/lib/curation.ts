"use client";
import { useCallback, useEffect, useState } from "react";

/** 每张图的唯一标识：master 用 ratio key（1x1/long/.../front/side/detail），尺寸图用 size_white/size_template。 */
export type ImageKey = string;

interface Curation {
  main: ImageKey[];   // 主图列表（顺序敏感）
  detail: ImageKey[]; // 详情图列表（顺序敏感）
}

const DEFAULT_MAIN: ImageKey[] = [
  "img0:1x1", "img0:long", "img0:3x4", "img0:9x16", "img0:16x9",
  "img0:front", "img0:side", "img0:detail",
];
const DEFAULT_DETAIL: ImageKey[] = ["img0:1x1", "img0:long"];

/** 把旧的 ratio key（如 "1x1"）规整为新格式 "img0:1x1"。size_<style> / img<N>:<ratio> 不变。 */
function migrateKey(k: string): string {
  if (k.startsWith("img") || k.startsWith("size_")) return k;
  return `img0:${k}`;
}

/** main curation 按变体存（每色一份主图列表）；detail 按产品存（跨变体共享配置）。 */
function mainKey(variantId: string) { return `img2ec:curation:main:${variantId}`; }
function detailKey(productId: string) { return `img2ec:curation:detail:${productId}`; }

function load(productId: string, variantId: string): Curation {
  if (typeof window === "undefined") return { main: DEFAULT_MAIN, detail: DEFAULT_DETAIL };
  try {
    const m = JSON.parse(localStorage.getItem(mainKey(variantId)) || "null");
    const d = JSON.parse(localStorage.getItem(detailKey(productId)) || "null");
    return {
      main: Array.isArray(m) ? m.map(migrateKey) : DEFAULT_MAIN,
      detail: Array.isArray(d) ? d.map(migrateKey) : DEFAULT_DETAIL,
    };
  } catch {
    return { main: DEFAULT_MAIN, detail: DEFAULT_DETAIL };
  }
}

function save(productId: string, variantId: string, c: Curation) {
  try {
    localStorage.setItem(mainKey(variantId), JSON.stringify(c.main));
    localStorage.setItem(detailKey(productId), JSON.stringify(c.detail));
  } catch {}
}

const listeners = new Set<() => void>();
function broadcast() { listeners.forEach((fn) => fn()); }

export function useCuration(productId: string | undefined, variantId: string | undefined) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((x) => x + 1);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);

  const cur = productId && variantId
    ? load(productId, variantId)
    : { main: DEFAULT_MAIN, detail: DEFAULT_DETAIL };

  const update = useCallback((mut: (c: Curation) => Curation) => {
    if (!productId || !variantId) return;
    const next = mut(load(productId, variantId));
    save(productId, variantId, next);
    broadcast();
  }, [productId, variantId]);

  const isInMain = (k: ImageKey) => cur.main.includes(k);
  const isInDetail = (k: ImageKey) => cur.detail.includes(k);

  const toggleMain = (k: ImageKey) =>
    update((c) => ({ ...c, main: c.main.includes(k) ? c.main.filter((x) => x !== k) : [...c.main, k] }));
  const toggleDetail = (k: ImageKey) =>
    update((c) => ({ ...c, detail: c.detail.includes(k) ? c.detail.filter((x) => x !== k) : [...c.detail, k] }));

  const reorderMain = (from: number, to: number) =>
    update((c) => {
      const next = [...c.main];
      const [m] = next.splice(from, 1);
      next.splice(to, 0, m);
      return { ...c, main: next };
    });
  const reorderDetail = (from: number, to: number) =>
    update((c) => {
      const next = [...c.detail];
      const [m] = next.splice(from, 1);
      next.splice(to, 0, m);
      return { ...c, detail: next };
    });

  const reset = () => {
    if (!productId || !variantId) return;
    try {
      localStorage.removeItem(mainKey(variantId));
      localStorage.removeItem(detailKey(productId));
    } catch {}
    broadcast();
  };

  // Used by external callers to silently sync state changes (e.g., after apply)
  const _ = tick; void _;

  return { main: cur.main, detail: cur.detail, isInMain, isInDetail, toggleMain, toggleDetail, reorderMain, reorderDetail, reset };
}
