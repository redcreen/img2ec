/** 统一空态：图标 + 主标题 + 副说明 +（可选）一个 CTA。 */
import type { ReactNode } from "react";

export function EmptyState({
  icon = "📂", title, hint, cta,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  cta?: { label: string; onClick: () => void };
}) {
  return (
    <div className="bg-zinc-950/50 border border-dashed border-zinc-700 rounded-lg py-8 px-4 text-center">
      <div className="text-3xl opacity-50 mb-2">{icon}</div>
      <div className="text-sm font-semibold mb-1">{title}</div>
      {hint && <div className="text-xs opacity-60 mb-3">{hint}</div>}
      {cta && (
        <button
          onClick={cta.onClick}
          className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded font-semibold"
        >{cta.label}</button>
      )}
    </div>
  );
}
