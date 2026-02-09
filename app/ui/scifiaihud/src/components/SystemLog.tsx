import { motion } from 'motion/react';
import { Terminal, ChevronRight } from 'lucide-react';
import { useEffect, useState } from 'react';

interface SystemLogProps {
  lines: string[];
}

export function SystemLog({ lines = [] }: SystemLogProps) {
  const [scrollKey, setScrollKey] = useState(0);

  useEffect(() => {
    // trigger small animation on update
    setScrollKey((k) => k + 1);
  }, [lines]);

  return (
    <div className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm relative overflow-hidden shadow-lg shadow-cyan-500/10">
      <div className="border-b border-cyan-500/30 p-3 flex items-center gap-2">
        <Terminal className="w-5 h-5" />
        <span className="text-xs">SYSTEM TERMINAL</span>
      </div>

      <div className="p-3 space-y-1 font-mono text-xs max-h-40 overflow-y-auto">
        {lines.map((line, idx) => (
          <motion.div
            key={`${scrollKey}-${idx}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 text-green-400"
          >
            <ChevronRight className="w-3 h-3 flex-shrink-0" />
            <span className="flex-1 break-all">{line}</span>
          </motion.div>
        ))}
        <motion.div
          className="flex items-center gap-2"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        >
          <ChevronRight className="w-3 h-3 text-cyan-400" />
          <span className="text-cyan-400">_</span>
        </motion.div>
      </div>
    </div>
  );
}
