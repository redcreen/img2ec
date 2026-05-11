"use client";
import { useEffect, useState } from "react";

/** localStorage key 前缀：图片打分 */
const KEY = "img2ec:rating:v1";

export type Rating = "good" | "bad" | null;

interface RatingMap {
  [url: string]: "good" | "bad";
}

function load(): RatingMap {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}") as RatingMap;
  } catch {
    return {};
  }
}

function save(map: RatingMap) {
  try {
    localStorage.setItem(KEY, JSON.stringify(map));
  } catch {
    /* localStorage 满 / private 模式 */
  }
}

// 简单 pub/sub，让所有用 useRating 的组件同步
const listeners = new Set<() => void>();
function broadcast() {
  listeners.forEach((fn) => fn());
}

export function getRating(url: string): Rating {
  return load()[url] ?? null;
}

export function setRating(url: string, r: Rating) {
  const map = load();
  if (r === null) delete map[url];
  else map[url] = r;
  save(map);
  broadcast();
}

export function useRating(url: string | null | undefined): [Rating, (r: Rating) => void] {
  const [_, force] = useState(0);
  useEffect(() => {
    const fn = () => force((x) => x + 1);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);
  const cur = url ? getRating(url) : null;
  const upd = (r: Rating) => {
    if (!url) return;
    setRating(url, r);
  };
  return [cur, upd];
}
