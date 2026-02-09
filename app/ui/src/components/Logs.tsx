import { motion, AnimatePresence } from 'motion/react';
import { FileText, AlertTriangle, Info, CheckCircle } from 'lucide-react';

interface LogsProps {
  logs: string[];
}

interface LogEntry {
  id: string;
  type: 'info' | 'warning' | 'success' | 'error';
  message: string;
  timestamp: string;
}

function parseLog(line: string): LogEntry {
  return {
    id: line,
    type: line.toLowerCase().includes("error")
      ? "error"
      : line.toLowerCase().includes("warn")
      ? "warning"
      : "info",
    message: line,
    timestamp: "",
  };
}

export function Logs({ logs }: LogsProps) {
  const parsed = (logs || []).map(parseLog).slice(-50);

  const getIcon = (type: LogEntry['type']) => {
    switch (type) {
      case 'info':
        return <Info className="w-3 h-3 text-cyan-400" />;
      case 'warning':
        return <AlertTriangle className="w-3 h-3 text-yellow-400" />;
      case 'success':
        return <CheckCircle className="w-3 h-3 text-green-400" />;
      case 'error':
        return <AlertTriangle className="w-3 h-3 text-red-400" />;
    }
  };

  const getColor = (type: LogEntry['type']) => {
    switch (type) {
      case 'info':
        return 'border-cyan-500/20';
      case 'warning':
        return 'border-yellow-500/20';
      case 'success':
        return 'border-green-500/20';
      case 'error':
        return 'border-red-500/20';
    }
  };

  return (
    <div className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm h-[calc(100vh-180px)] flex flex-col relative overflow-hidden shadow-lg shadow-cyan-500/10">
      <div className="border-b border-cyan-500/30 p-3 flex items-center gap-2">
        <FileText className="w-5 h-5" />
        <span className="text-xs">SYSTEM LOGS</span>
        <motion.div
          className="ml-auto w-2 h-2 bg-cyan-400 rounded-full"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <AnimatePresence>
          {parsed.map((log) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, x: -20, height: 0 }}
              animate={{ opacity: 1, x: 0, height: 'auto' }}
              exit={{ opacity: 0, x: 20, height: 0 }}
              className={`border ${getColor(log.type)} bg-black/40 p-2`}
            >
              <div className="flex items-start gap-2">
                <div className="mt-0.5">{getIcon(log.type)}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-cyan-600">{log.timestamp}</div>
                  <div className="text-xs mt-1 break-words">{log.message}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <div className="border-t border-cyan-500/30 p-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-cyan-600">TOTAL ENTRIES</span>
          <span>{logs.length}</span>
        </div>
      </div>
    </div>
  );
}
