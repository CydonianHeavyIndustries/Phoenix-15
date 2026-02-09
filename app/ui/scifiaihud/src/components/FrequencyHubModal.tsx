import { motion, AnimatePresence } from 'motion/react';
import { X, Waves } from 'lucide-react';
import { FrequencyOrb } from './FrequencyOrb';
import { FrequencyLab } from './FrequencyLab';

interface FrequencyHubModalProps {
  open: boolean;
  onClose: () => void;
}

export function FrequencyHubModal({ open, onClose }: FrequencyHubModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/80 backdrop-blur z-[120] flex items-center justify-center p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="bg-slate-950 border-2 border-cyan-500/50 rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-y-auto relative p-4 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-cyan-500/30 pb-3">
              <div className="flex items-center gap-3 text-cyan-200">
                <Waves className="w-6 h-6" />
                <div>
                  <div className="text-sm uppercase tracking-widest">Frequency Hub</div>
                  <div className="text-xs text-cyan-400/80">
                    Cymatic analyzer + generator + emotion mapping in one place.
                  </div>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 border border-cyan-500/40 rounded hover:bg-cyan-500/10 transition-colors"
              >
                <X className="w-5 h-5 text-cyan-200" />
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <FrequencyOrb />
              <FrequencyLab />
            </div>

            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 border border-cyan-500/40 rounded hover:bg-cyan-500/10 transition-colors text-sm"
              >
                Close
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
