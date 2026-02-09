import React from "react";
import { Brain } from "lucide-react";

export function MemoryCheckButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-2 border border-cyan-500/50 bg-cyan-500/10 hover:bg-cyan-500/20 transition-colors text-xs flex items-center gap-2"
    >
      <Brain className="w-4 h-4" />
      Memory Check
    </button>
  );
}
