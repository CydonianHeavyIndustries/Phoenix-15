import { motion } from 'motion/react';
import { useEffect, useState } from 'react';

interface OrbVisualizerProps {
  status: 'idle' | 'speaking' | 'listening';
  isAwake: boolean;
}

export function OrbVisualizer({ status, isAwake }: OrbVisualizerProps) {
  const [frequencyBars, setFrequencyBars] = useState<number[]>(Array(32).fill(0));
  const [wavePoints, setWavePoints] = useState<number[]>(Array(50).fill(0));
  const [innerWavePoints, setInnerWavePoints] = useState<number[]>(Array(30).fill(0));

  useEffect(() => {
    if (!isAwake) {
      setFrequencyBars(Array(32).fill(0));
      setWavePoints(Array(50).fill(0));
      setInnerWavePoints(Array(30).fill(0));
      return;
    }

    const interval = setInterval(() => {
      // Different patterns based on status
      if (status === 'speaking') {
        // Active speaking pattern - high energy
        setFrequencyBars(Array(32).fill(0).map(() => Math.random() * 100));
        setWavePoints(Array(50).fill(0).map((_, i) => 
          Math.sin(i * 0.2 + Date.now() * 0.01) * 30 + Math.random() * 20
        ));
        setInnerWavePoints(Array(30).fill(0).map((_, i) => 
          Math.cos(i * 0.3 + Date.now() * 0.015) * 20 + Math.random() * 15
        ));
      } else if (status === 'listening') {
        // Listening pattern - responsive but calmer
        setFrequencyBars(Array(32).fill(0).map(() => Math.random() * 60 + 20));
        setWavePoints(Array(50).fill(0).map((_, i) => 
          Math.sin(i * 0.15 + Date.now() * 0.008) * 25
        ));
        setInnerWavePoints(Array(30).fill(0).map((_, i) => 
          Math.cos(i * 0.2 + Date.now() * 0.01) * 15
        ));
      } else {
        // Idle pattern - breathing, subtle
        setFrequencyBars(Array(32).fill(0).map((_, i) => 
          Math.sin(i * 0.5 + Date.now() * 0.003) * 20 + 15
        ));
        setWavePoints(Array(50).fill(0).map((_, i) => 
          Math.sin(i * 0.1 + Date.now() * 0.005) * 15
        ));
        setInnerWavePoints(Array(30).fill(0).map((_, i) => 
          Math.cos(i * 0.15 + Date.now() * 0.006) * 10
        ));
      }
    }, 50);

    return () => clearInterval(interval);
  }, [status, isAwake]);

  const getColorScheme = () => {
    if (!isAwake) return {
      primary: 'rgba(100, 116, 139, 0.3)',
      secondary: 'rgba(71, 85, 105, 0.2)',
      glow: 'rgba(100, 116, 139, 0.1)'
    };
    
    switch (status) {
      case 'speaking':
        return {
          primary: 'rgba(236, 72, 153, 0.8)', // Pink/magenta
          secondary: 'rgba(139, 92, 246, 0.6)', // Purple
          tertiary: 'rgba(6, 182, 212, 0.8)', // Cyan
          glow: 'rgba(236, 72, 153, 0.4)'
        };
      case 'listening':
        return {
          primary: 'rgba(34, 211, 238, 0.8)', // Cyan
          secondary: 'rgba(14, 165, 233, 0.6)', // Blue
          tertiary: 'rgba(6, 182, 212, 0.8)', // Teal
          glow: 'rgba(34, 211, 238, 0.4)'
        };
      default:
        return {
          primary: 'rgba(6, 182, 212, 0.6)', // Teal
          secondary: 'rgba(20, 184, 166, 0.5)', // Teal lighter
          tertiary: 'rgba(34, 211, 238, 0.4)', // Cyan
          glow: 'rgba(6, 182, 212, 0.3)'
        };
    }
  };

  const colors = getColorScheme();
  const centerX = 150;
  const centerY = 150;
  const baseRadius = 60;

  // Generate wave path
  const generateWavePath = (points: number[], radius: number, amplitude: number) => {
    const angleStep = (Math.PI * 2) / points.length;
    let path = '';
    
    points.forEach((point, i) => {
      const angle = i * angleStep;
      const r = radius + point * (amplitude / 100);
      const x = centerX + Math.cos(angle) * r;
      const y = centerY + Math.sin(angle) * r;
      
      if (i === 0) {
        path += `M ${x} ${y}`;
      } else {
        path += ` L ${x} ${y}`;
      }
    });
    
    path += ' Z';
    return path;
  };

  return (
    <div className="border border-cyan-500/30 bg-gradient-to-br from-slate-900/50 to-teal-900/30 backdrop-blur-sm p-6 relative overflow-hidden aspect-square">
      {/* Glow effect */}
      {isAwake && (
        <motion.div
          className="absolute inset-0 blur-2xl"
          style={{ background: colors.glow }}
          animate={{
            opacity: [0.3, 0.6, 0.3],
            scale: [0.8, 1, 0.8]
          }}
          transition={{ duration: 3, repeat: Infinity }}
        />
      )}

      <div className="relative w-full h-full flex items-center justify-center">
        <svg width="300" height="300" viewBox="0 0 300 300" className="absolute">
          {/* Outer frequency ring */}
          {isAwake && frequencyBars.map((height, i) => {
            const angle = (i * 360) / frequencyBars.length;
            const innerRadius = 110;
            const outerRadius = 110 + (height * 0.4);
            const x1 = centerX + Math.cos((angle * Math.PI) / 180) * innerRadius;
            const y1 = centerY + Math.sin((angle * Math.PI) / 180) * innerRadius;
            const x2 = centerX + Math.cos((angle * Math.PI) / 180) * outerRadius;
            const y2 = centerY + Math.sin((angle * Math.PI) / 180) * outerRadius;

            return (
              <motion.line
                key={`bar-${i}`}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={colors.primary}
                strokeWidth="2"
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.4, 0.8, 0.4] }}
                transition={{ duration: 0.5, delay: i * 0.01, repeat: Infinity }}
              />
            );
          })}

          {/* Outer wave form */}
          {isAwake && (
            <motion.path
              d={generateWavePath(wavePoints, 90, 0.8)}
              fill="none"
              stroke={colors.primary}
              strokeWidth="2"
              initial={{ pathLength: 0 }}
              animate={{ 
                pathLength: 1,
                opacity: [0.6, 0.9, 0.6]
              }}
              transition={{ 
                pathLength: { duration: 2 },
                opacity: { duration: 2, repeat: Infinity }
              }}
            />
          )}

          {/* Middle wave form */}
          {isAwake && (
            <motion.path
              d={generateWavePath(innerWavePoints, 70, 0.6)}
              fill="none"
              stroke={colors.secondary || colors.primary}
              strokeWidth="3"
              animate={{ 
                opacity: [0.5, 0.8, 0.5]
              }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
          )}

          {/* Inner flowing wave */}
          {isAwake && status === 'speaking' && (
            <motion.path
              d={generateWavePath(innerWavePoints, 50, 1)}
              fill={colors.tertiary || colors.secondary}
              opacity="0.3"
              animate={{ 
                scale: [0.95, 1.05, 0.95]
              }}
              transition={{ duration: 1, repeat: Infinity }}
              style={{ transformOrigin: 'center' }}
            />
          )}

          {/* Core orb */}
          <motion.circle
            cx={centerX}
            cy={centerY}
            r={baseRadius}
            fill={`url(#orbGradient-${status})`}
            animate={isAwake ? {
              r: status === 'speaking' ? [baseRadius, baseRadius + 5, baseRadius] : [baseRadius, baseRadius + 2, baseRadius],
            } : {}}
            transition={{ duration: status === 'speaking' ? 0.6 : 2, repeat: Infinity }}
          />

          {/* Inner glow */}
          {isAwake && (
            <motion.circle
              cx={centerX}
              cy={centerY}
              r={baseRadius * 0.6}
              fill="rgba(255, 255, 255, 0.2)"
              animate={{
                opacity: [0.2, 0.4, 0.2],
                r: [baseRadius * 0.5, baseRadius * 0.7, baseRadius * 0.5]
              }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          )}

          {/* Rotating particles */}
          {isAwake && [0, 1, 2].map((ring) => (
            <g key={`ring-${ring}`}>
              {Array.from({ length: 8 }).map((_, i) => {
                const angle = (i * 360) / 8 + ring * 15;
                const radius = 85 + ring * 10;
                return (
                  <motion.circle
                    key={`particle-${ring}-${i}`}
                    cx={centerX}
                    cy={centerY}
                    r="2"
                    fill={colors.primary}
                    animate={{
                      cx: centerX + Math.cos((angle * Math.PI) / 180) * radius,
                      cy: centerY + Math.sin((angle * Math.PI) / 180) * radius,
                      opacity: [0.3, 0.8, 0.3]
                    }}
                    transition={{
                      cx: { duration: 5 + ring, repeat: Infinity, ease: 'linear' },
                      cy: { duration: 5 + ring, repeat: Infinity, ease: 'linear' },
                      opacity: { duration: 1.5, repeat: Infinity, delay: i * 0.1 }
                    }}
                  />
                );
              })}
            </g>
          ))}

          {/* Gradient definitions */}
          <defs>
            <radialGradient id="orbGradient-idle">
              <stop offset="0%" stopColor={colors.primary} />
              <stop offset="100%" stopColor={colors.secondary || colors.primary} />
            </radialGradient>
            <radialGradient id="orbGradient-speaking">
              <stop offset="0%" stopColor="rgba(236, 72, 153, 0.8)" />
              <stop offset="50%" stopColor="rgba(139, 92, 246, 0.6)" />
              <stop offset="100%" stopColor="rgba(6, 182, 212, 0.8)" />
            </radialGradient>
            <radialGradient id="orbGradient-listening">
              <stop offset="0%" stopColor="rgba(34, 211, 238, 0.9)" />
              <stop offset="100%" stopColor="rgba(14, 165, 233, 0.7)" />
            </radialGradient>
          </defs>
        </svg>

        {/* Status label */}
        <div className="absolute bottom-4 left-0 right-0 text-center">
          <motion.div 
            className="text-xs text-cyan-600"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            NEURAL CORE
          </motion.div>
          <div className={`text-xs mt-1 ${
            !isAwake ? 'text-gray-500' :
            status === 'speaking' ? 'text-pink-400' :
            status === 'listening' ? 'text-cyan-400' :
            'text-teal-400'
          }`}>
            {isAwake ? status.toUpperCase() : 'DORMANT'}
          </div>
        </div>
      </div>
    </div>
  );
}
