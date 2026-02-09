import { motion } from 'motion/react';
import { Terminal, ChevronRight } from 'lucide-react';
import { useEffect, useState } from 'react';

interface SystemLogProps {
  logs: string[];
  onTerminal: (command: string) => Promise<any>;
}

export function SystemLog({ logs, onTerminal }: SystemLogProps) {
  const [cmd, setCmd] = useState('');
  const [out, setOut] = useState<string[]>([]);

  // Clear local terminal output when new session logs arrive empty (fresh session)
  useEffect(() => {
    if (logs.length === 0) {
      setOut([]);
    }
  }, [logs]);

  const handleSend = async () => {
    if (!cmd.trim()) return;
    const res = await onTerminal(cmd);
    const text = res?.output ?? 'OK';
    setOut(prev => [...prev, `$ ${cmd}`, text].slice(-20));
    setCmd('');
  };

  return (
    <div className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm relative overflow-hidden shadow-lg shadow-cyan-500/10">
      <div className="border-b border-cyan-500/30 p-3 flex items-center gap-2">
        <Terminal className="w-5 h-5" />
        <span className="text-xs">SYSTEM TERMINAL</span>
      </div>

      <div className="p-3 space-y-1 font-mono text-xs max-h-40 overflow-y-auto">
        {logs.map((line, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 text-green-400"
          >
            <ChevronRight className="w-3 h-3 flex-shrink-0" />
            <span className="flex-1">{line}</span>
          </motion.div>
        ))}
        {out.map((line, idx) => (
          <motion.div
            key={`out-${idx}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 text-cyan-300"
          >
            <ChevronRight className="w-3 h-3 flex-shrink-0" />
            <span className="flex-1">{line}</span>
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
      <div className="border-t border-cyan-500/30 p-2 flex gap-2">
        <input
          className="flex-1 bg-black border border-cyan-500/30 px-2 py-1 text-xs"
          value={cmd}
          onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Enter command..."
        />
        <button
          onClick={handleSend}
          className="px-3 py-1 text-xs border border-cyan-500/50 hover:bg-cyan-500/10"
        >
          Send
        </button>
      </div>
    </div>
  );
}
