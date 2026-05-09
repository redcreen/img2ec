import type { Scene } from "@/lib/types";

export function SceneCard({ scene, onClick }: { scene: Scene; onClick?: () => void }) {
  return (
    <div onClick={onClick}
      className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-2 cursor-pointer transition">
      <div className="w-full h-28 bg-gradient-to-br from-amber-200 to-amber-900 rounded mb-2 relative flex items-center justify-center">
        <span className="absolute top-1.5 left-1.5 bg-black/55 text-white text-[10px] px-1.5 py-0.5 rounded">
          {scene.category}
        </span>
        <div className="w-1/2 h-1/2 bg-white/70 rounded shadow-md" />
      </div>
      <h3 className="text-xs font-semibold">{scene.name}</h3>
      <p className="text-[10px] opacity-55 line-clamp-2">{scene.desc || scene.prompt.slice(0, 60)}</p>
    </div>
  );
}
