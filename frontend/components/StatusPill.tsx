import type { SKUStatus, ImageStatus } from "@/lib/types";

const labels: Record<string, string> = {
  draft: "编辑中", ready: "待处理", running: "处理中",
  done: "已完成", error: "部分失败",
  pending: "排队", cutting: "抠图中", generating: "生 master 中",
  composing: "派生中", failed: "失败",
};

const styles: Record<string, string> = {
  draft: "bg-zinc-700 text-zinc-300",
  ready: "bg-blue-900/50 text-blue-300",
  pending: "bg-blue-900/50 text-blue-300",
  running: "bg-amber-900/50 text-amber-300",
  cutting: "bg-amber-900/50 text-amber-300",
  generating: "bg-amber-900/50 text-amber-300",
  composing: "bg-amber-900/50 text-amber-300",
  done: "bg-green-900/50 text-green-300",
  error: "bg-red-900/50 text-red-300",
  failed: "bg-red-900/50 text-red-300",
};

export function StatusPill({ status }: { status: SKUStatus | ImageStatus }) {
  return <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${styles[status]}`}>{labels[status]}</span>;
}
