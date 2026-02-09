import { motion } from 'motion/react';
import { Power, Activity, FileText, Brain } from 'lucide-react';

interface WakeStripProps {
  isAwake: boolean;
  onWake: () => void;
  onSelfCheck: () => void;
  onOpenLogs: () => void;
  onMemoryCheck: () => void;
}

export function WakeStrip({ isAwake, onWake, onSelfCheck, onOpenLogs, onMemoryCheck }: WakeStripProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scaleY: 0 }}
      animate={{ opacity: 1, scaleY: 1 }}
      className="mt-4 border-2 border-cyan-400/60 bg-slate-900/80 backdrop-blur-sm p-4 relative overflow-hidden shadow-2xl shadow-cyan-400/30"
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
              ? 'border-emerald-400/60 bg-emerald-500/30 cursor-not-allowed shadow-lg shadow-emerald-400/50'
              : 'border-cyan-400/60 bg-cyan-500/20 hover:bg-cyan-500/30 hover:border-cyan-300 shadow-xl shadow-cyan-400/40'
          }`}
        >
          {!isAwake && (
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent"
              animate={{ x: ['-100%', '100%'] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          )}
          <div className="relative flex items-center gap-4">
            <Power className={`w-8 h-8 ${isAwake ? 'text-emerald-300' : 'text-cyan-300'}`} 
              style={{ filter: `drop-shadow(0 0 10px ${isAwake ? 'rgba(0, 255, 136, 0.8)' : 'rgba(0, 255, 209, 0.8)'})` }} />
            <div className="text-left">
              <div className={`text-xl ${isAwake ? 'text-emerald-300' : 'text-cyan-300'}`}
                style={{ textShadow: `0 0 15px ${isAwake ? 'rgba(0, 255, 136, 0.8)' : 'rgba(0, 255, 209, 0.8)'}` }}>
                {isAwake ? 'SYSTEMS ACTIVE' : 'WAKE SYSTEMS'}
              </div>
              <div className="text-xs text-cyan-400 mt-1">
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
            className={`px-6 py-4 border-2 transition-all flex items-center gap-2 ${
              isAwake
                ? 'border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-lg hover:shadow-cyan-400/30'
                : 'border-gray-700 text-gray-600 cursor-not-allowed'
            }`}
          >
            <Activity className="w-5 h-5" />
            <div className="text-left">
              <div className="text-xs text-cyan-300">SELF-CHECK</div>
              <div className="text-xs text-cyan-400">Run diagnostics</div>
            </div>
          </button>

          <button
            onClick={isAwake ? onOpenLogs : undefined}
            disabled={!isAwake}
            className={`px-6 py-4 border-2 transition-all flex items-center gap-2 ${
              isAwake
                ? 'border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-lg hover:shadow-cyan-400/30'
                : 'border-gray-700 text-gray-600 cursor-not-allowed'
            }`}
          >
            <FileText className="w-5 h-5" />
            <div className="text-left">
              <div className="text-xs text-cyan-300">OPEN LOGS</div>
              <div className="text-xs text-cyan-400">View full history</div>
            </div>
          </button>

          <button
            onClick={isAwake ? onMemoryCheck : undefined}
            disabled={!isAwake}
            className={`px-6 py-4 border-2 transition-all flex items-center gap-2 ${
              isAwake
                ? 'border-cyan-400/50 hover:bg-cyan-500/20 hover:shadow-lg hover:shadow-cyan-400/30'
                : 'border-gray-700 text-gray-600 cursor-not-allowed'
            }`}
          >
            <Brain className="w-5 h-5" />
            <div className="text-left">
              <div className="text-xs text-cyan-300">MEMORY CHECK</div>
              <div className="text-xs text-cyan-400">Validate & reload</div>
            </div>
          </button>
        </div>

        {/* Status Indicator */}
        {isAwake && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="ml-auto flex items-center gap-3 px-6 py-4 border-2 border-emerald-400/60 bg-emerald-500/20 shadow-lg shadow-emerald-400/30"
          >
            <motion.div
              className="w-3 h-3 bg-emerald-300 rounded-full shadow-lg"
              style={{ boxShadow: '0 0 15px rgba(0, 255, 136, 0.9)' }}
              animate={{ scale: [1, 1.3, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <div>
              <div className="text-xs text-emerald-300" style={{ textShadow: '0 0 10px rgba(0, 255, 136, 0.8)' }}>
                BOOT COMPLETE
              </div>
              <div className="text-xs text-cyan-400">Ready for commands</div>
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
