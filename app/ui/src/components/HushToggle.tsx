import { motion } from 'motion/react';
import { VolumeX } from 'lucide-react';

interface HushToggleProps {
  isHushed: boolean;
  onToggle: (value: boolean) => void;
}

export function HushToggle({ isHushed, onToggle }: HushToggleProps) {
  return (
    <div className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm p-4 relative overflow-hidden shadow-lg shadow-cyan-500/10">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <VolumeX className={`w-5 h-5 ${isHushed ? 'text-magenta-400' : 'text-cyan-400'}`} />
          <div>
            <div className="text-xs text-cyan-400">HUSH MODE</div>
            <div className="text-xs text-cyan-600 mt-0.5">
              {isHushed ? 'Audio output muted' : 'Audio output active'}
            </div>
          </div>
        </div>

        <button
          onClick={() => onToggle(!isHushed)}
          className={`relative w-16 h-8 border transition-all ${
            isHushed
              ? 'bg-magenta-500/20 border-magenta-500/50'
              : 'bg-black border-cyan-500/30'
          }`}
        >
          <motion.div
            className={`absolute top-1 w-6 h-6 ${
              isHushed ? 'bg-magenta-500' : 'bg-cyan-500'
            }`}
            animate={{ left: isHushed ? '36px' : '4px' }}
            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          />
        </button>
      </div>

      {isHushed && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-3 pt-3 border-t border-magenta-500/20"
        >
          <div className="flex items-center gap-2 text-xs text-magenta-400">
            <motion.div
              className="w-2 h-2 bg-magenta-400 rounded-full"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span>Silent mode engaged</span>
          </div>
        </motion.div>
      )}
    </div>
  );
}
