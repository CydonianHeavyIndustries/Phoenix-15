import { motion } from 'motion/react';
import { Smile, Brain, Zap, Heart } from 'lucide-react';
import { useEffect, useState } from 'react';

interface MoodCardProps {
  isAwake: boolean;
  moodLabel?: string;
  intensity?: number;
  homeState?: string;
  lastSync?: string;
}

export function MoodCard({ isAwake, moodLabel, intensity, homeState, lastSync }: MoodCardProps) {
  const [mood, setMood] = useState({
    emotion: moodLabel || 'Balanced',
    confidence: Math.round((intensity ?? 0.5) * 100),
    energy: Math.round((intensity ?? 0.5) * 100),
    engagement: 78
  });

  useEffect(() => {
    setMood({
      emotion: moodLabel || 'Balanced',
      confidence: Math.round((intensity ?? 0.5) * 100),
      energy: Math.round((intensity ?? 0.5) * 100),
      engagement: 78
    });
  }, [moodLabel, intensity]);

  const metrics = [
    { label: 'Confidence', value: mood.confidence, icon: Brain, color: '#00FFD1' },
    { label: 'Energy', value: mood.energy, icon: Zap, color: '#00FF88' },
    { label: 'Engagement', value: mood.engagement, icon: Heart, color: '#FF1E8E' }
  ];

  return (
    <div className="border-2 border-cyan-400/60 bg-gradient-to-br from-slate-900/80 to-cyan-950/60 backdrop-blur-sm p-6 relative overflow-hidden aspect-square flex flex-col shadow-2xl shadow-cyan-400/30">
      {/* Glow effect */}
      {isAwake && (
        <motion.div
          className="absolute inset-0 blur-2xl bg-cyan-400/20"
          animate={{
            opacity: [0.2, 0.4, 0.2],
            scale: [0.9, 1.1, 0.9]
          }}
          transition={{ duration: 3, repeat: Infinity }}
        />
      )}

      <div className="relative flex items-center gap-2 mb-4">
        <Smile className="w-5 h-5 text-cyan-300" style={{ filter: 'drop-shadow(0 0 6px rgba(0, 255, 209, 0.8))' }} />
        <span className="text-xs text-cyan-300">EMOTIONAL STATE</span>
      </div>

      <div className="relative flex-1 flex flex-col items-center justify-center">
        {/* Main mood display */}
        <motion.div
          className="text-center mb-6"
          animate={isAwake ? { scale: [1, 1.05, 1] } : {}}
          transition={{ duration: 3, repeat: Infinity }}
        >
          <div className="text-xs text-cyan-400 mb-2">CURRENT MOOD</div>
          <div className={`text-3xl ${isAwake ? 'text-cyan-300' : 'text-gray-500'}`}
            style={{ 
              textShadow: isAwake ? '0 0 20px rgba(0, 255, 209, 0.8)' : 'none'
            }}>
            {isAwake ? mood.emotion : 'Dormant'}
          </div>
          <div className="text-xs text-cyan-500 mt-1">{homeState ? `Home: ${homeState}` : ''}</div>
          <div className="text-[11px] text-cyan-700">{lastSync ? `Sync: ${lastSync}` : ''}</div>
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
                  <metric.icon className="w-3 h-3 text-cyan-300" />
                  <span className="text-cyan-400">{metric.label}</span>
                </div>
                <span className="text-cyan-300" style={{ 
                  textShadow: isAwake ? '0 0 8px rgba(0, 255, 209, 0.6)' : 'none' 
                }}>
                  {isAwake ? `${metric.value}%` : '--'}
                </span>
              </div>
              <div className="h-1.5 bg-black border border-cyan-400/40 relative overflow-hidden">
                <motion.div
                  className="h-full"
                  style={{ 
                    background: `linear-gradient(90deg, ${metric.color}, ${metric.color}CC)`,
                    boxShadow: isAwake ? `0 0 10px ${metric.color}` : 'none'
                  }}
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
