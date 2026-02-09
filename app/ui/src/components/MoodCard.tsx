import { motion } from 'motion/react';
import { Smile, Brain, Zap, Heart } from 'lucide-react';
interface MoodCardProps {
  isAwake: boolean;
  mood: { label: string; tone: string; intensity: number };
}

export function MoodCard({ isAwake, mood }: MoodCardProps) {
  const mapped = {
    emotion: mood.label || 'Neutral',
    confidence: Math.min(100, Math.max(0, Math.round((mood.intensity ?? 0.5) * 100))),
    energy: Math.min(100, Math.max(0, Math.round((mood.intensity ?? 0.5) * 100))),
    engagement: Math.min(100, Math.max(0, Math.round((mood.intensity ?? 0.5) * 100))),
  };

  const metrics = [
    { label: 'Confidence', value: mapped.confidence, icon: Brain, color: 'cyan' },
    { label: 'Energy', value: mapped.energy, icon: Zap, color: 'yellow' },
    { label: 'Engagement', value: mapped.engagement, icon: Heart, color: 'pink' }
  ];

  return (
    <div className="border border-cyan-500/30 bg-gradient-to-br from-slate-900/50 to-teal-900/30 backdrop-blur-sm p-6 relative overflow-hidden aspect-square flex flex-col shadow-lg shadow-cyan-500/10">
      <div className="flex items-center gap-2 mb-4">
        <Smile className="w-5 h-5 text-cyan-400" />
        <span className="text-xs">EMOTIONAL STATE</span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center">
        {/* Main mood display */}
        <motion.div
          className="text-center mb-6"
          animate={isAwake ? { scale: [1, 1.05, 1] } : {}}
          transition={{ duration: 3, repeat: Infinity }}
        >
          <div className="text-xs text-cyan-600 mb-2">CURRENT MOOD</div>
          <div className={`text-2xl ${isAwake ? 'text-cyan-400' : 'text-gray-500'}`}>
            {isAwake ? mapped.emotion : 'Dormant'}
          </div>
        </motion.div>

        {/* Metrics */}
        <div className="w-full space-y-3">
          {metrics.map((metric, index) => (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="space-y-1"
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <metric.icon className="w-3 h-3" />
                  <span className="text-cyan-600">{metric.label}</span>
                </div>
                <span className="text-cyan-400">{isAwake ? `${metric.value}%` : '--'}</span>
              </div>
              <div className="h-1 bg-black border border-cyan-500/20 relative overflow-hidden">
                <motion.div
                  className={`h-full bg-gradient-to-r from-${metric.color}-500/50 to-${metric.color}-400`}
                  initial={{ width: 0 }}
                  animate={{ width: isAwake ? `${metric.value}%` : '0%' }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
