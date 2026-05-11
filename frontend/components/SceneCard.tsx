import type { Scene } from "@/lib/types";

export function SceneCard({ scene, onClick }: { scene: Scene; onClick?: () => void }) {
  return (
    <div onClick={onClick}
      className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-2 cursor-pointer transition">
      <div className="w-full h-28 rounded mb-2 relative overflow-hidden bg-zinc-800">
        {scene.cover_url ? (
          <img src={scene.cover_url} alt={scene.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-zinc-700 to-zinc-900 flex items-center justify-center text-[10px] opacity-50">
            无代表图
          </div>
        )}
        <span className="absolute top-1.5 left-1.5 bg-black/65 text-white text-[10px] px-1.5 py-0.5 rounded">
          {scene.category}
        </span>
      </div>
      <h3 className="text-xs font-semibold">{scene.name}</h3>
      <p className="text-[10px] opacity-55 line-clamp-2">{scene.desc || scene.prompt.slice(0, 60)}</p>
    </div>
  );
}
