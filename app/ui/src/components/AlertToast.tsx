import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, CheckCircle, X, Info } from 'lucide-react';

interface AlertToastProps {
  type: 'error' | 'warning' | 'success' | 'info';
  message: string;
  onClose: () => void;
}

export function AlertToast({ type, message, onClose }: AlertToastProps) {
  const getIcon = () => {
    switch (type) {
      case 'error':
        return <AlertTriangle className="w-5 h-5 text-red-400" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'info':
        return <Info className="w-5 h-5 text-cyan-400" />;
    }
  };

  const getBorderColor = () => {
    switch (type) {
      case 'error':
        return 'border-red-500/50';
      case 'warning':
        return 'border-yellow-500/50';
      case 'success':
        return 'border-green-500/50';
      case 'info':
        return 'border-cyan-500/50';
    }
  };

  const getBgColor = () => {
    switch (type) {
      case 'error':
        return 'bg-red-500/10';
      case 'warning':
        return 'bg-yellow-500/10';
      case 'success':
        return 'bg-green-500/10';
      case 'info':
        return 'bg-cyan-500/10';
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -50, x: '-50%' }}
        animate={{ opacity: 1, y: 0, x: '-50%' }}
        exit={{ opacity: 0, y: -50, x: '-50%' }}
        className="fixed top-20 left-1/2 z-50 max-w-md w-full px-4"
      >
        <div className={`border-2 ${getBorderColor()} ${getBgColor()} bg-black/90 backdrop-blur-sm p-4 relative overflow-hidden`}>
          {/* Animated border effect */}
          <motion.div
            className="absolute inset-0 pointer-events-none opacity-50"
            style={{
              background: `linear-gradient(90deg, transparent, ${
                type === 'error' ? 'rgba(255, 0, 0, 0.3)' :
                type === 'warning' ? 'rgba(255, 255, 0, 0.3)' :
                type === 'success' ? 'rgba(0, 255, 0, 0.3)' :
                'rgba(0, 255, 255, 0.3)'
              }, transparent)`,
            }}
            animate={{ x: ['-100%', '100%'] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          />

          <div className="relative flex items-start gap-3">
            {getIcon()}
            <div className="flex-1">
              <div className="text-xs text-cyan-600 mb-1">
                {type.toUpperCase()} ALERT
              </div>
              <div className="text-sm text-cyan-400">{message}</div>
            </div>
            <button
              onClick={onClose}
              className="p-1 hover:bg-cyan-500/10 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
