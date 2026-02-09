import { motion } from 'motion/react';
import { Power, Activity, FileText } from 'lucide-react';

interface WakeStripProps {
  isAwake: boolean;
  onWake: () => void;
  onSelfCheck: () => void;
  onOpenLogs?: () => void;
}

export function WakeStrip({ isAwake, onWake, onSelfCheck, onOpenLogs }: WakeStripProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scaleY: 0 }}
      animate={{ opacity: 1, scaleY: 1 }}
      className="mt-4 border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm p-4 relative overflow-hidden shadow-lg shadow-cyan-500/10"
    >
      <div className="flex items-center gap-4">
        {/* Large Wake Button */}
        <motion.button
          onClick={onWake}
          disabled={isAwake}
          whileHover={{ scale: isAwake ? 1 : 1.02 }}
          whileTap={{ scale: isAwake ? 1 : 0.98 }}
          className={`relative px-12 py-6 border-2 transition-all ${
            isAwake
              ? 'border-green-500/50 bg-green-500/20 cursor-not-allowed'
              : 'border-cyan-500/50 bg-cyan-500/10 hover:bg-cyan-500/20 hover:border-cyan-500'
          }`}
        >
          {!isAwake && (
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent"
              animate={{ x: ['-100%', '100%'] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          )}
          <div className="relative flex items-center gap-4">
            <Power className={`w-8 h-8 ${isAwake ? 'text-green-400' : 'text-cyan-400'}`} />
            <div className="text-left">
              <div className={`text-xl ${isAwake ? 'text-green-400' : 'text-cyan-400'}`}>
                {isAwake ? 'SYSTEMS ACTIVE' : 'WAKE SYSTEMS'}
              </div>
              <div className="text-xs text-cyan-600 mt-1">
                {isAwake ? 'All subsystems operational' : 'Initialize AI core and peripherals'}
              </div>
            </div>
          </div>
        </motion.button>

        {/* Quick Actions */}
        <div className="flex gap-3">
          <button
            onClick={onSelfCheck}
            disabled={!isAwake}
            className={`px-6 py-4 border transition-colors flex items-center gap-2 ${
              isAwake
                ? 'border-cyan-500/30 hover:bg-cyan-500/10'
                : 'border-gray-700 text-gray-600 cursor-not-allowed'
            }`}
          >
            <Activity className="w-5 h-5" />
            <div className="text-left">
              <div className="text-xs">SELF-CHECK</div>
              <div className="text-xs text-cyan-600">Run diagnostics</div>
            </div>
          </button>

          <button
            onClick={onOpenLogs}
            disabled={!isAwake}
            className={`px-6 py-4 border transition-colors flex items-center gap-2 ${
              isAwake
                ? 'border-cyan-500/30 hover:bg-cyan-500/10'
                : 'border-gray-700 text-gray-600 cursor-not-allowed'
            }`}
          >
            <FileText className="w-5 h-5" />
            <div className="text-left">
              <div className="text-xs">OPEN LOGS</div>
              <div className="text-xs text-cyan-600">View full history</div>
            </div>
          </button>
        </div>

        {/* Status Indicator */}
        {isAwake && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="ml-auto flex items-center gap-3 px-6 py-4 border border-green-500/30 bg-green-500/10"
          >
            <motion.div
              className="w-3 h-3 bg-green-400 rounded-full"
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <div>
              <div className="text-xs text-green-400">BOOT COMPLETE</div>
              <div className="text-xs text-cyan-600">Ready for commands</div>
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
