import { motion } from 'motion/react';
import { useEffect, useState } from 'react';

interface OrbVisualizerProps {
  status: 'idle' | 'speaking' | 'listening' | 'thinking';
  isAwake: boolean;
}

export function OrbVisualizer({ status, isAwake }: OrbVisualizerProps) {
  const [frequencyBars, setFrequencyBars] = useState<number[]>(Array(40).fill(0));
  const [wavePoints, setWavePoints] = useState<number[]>(Array(60).fill(0));
  const [innerWavePoints, setInnerWavePoints] = useState<number[]>(Array(40).fill(0));
  const [spectrum, setSpectrum] = useState<number[]>(Array(24).fill(0));

  useEffect(() => {
    if (!isAwake) {
      setFrequencyBars(Array(40).fill(0));
      setWavePoints(Array(60).fill(0));
      setInnerWavePoints(Array(40).fill(0));
      setSpectrum(Array(24).fill(0));
      return;
    }

    const interval = setInterval(() => {
      // Different patterns based on status
      if (status === 'speaking') {
        // Active speaking pattern - high energy
        setFrequencyBars(Array(40).fill(0).map(() => Math.random() * 100));
        setWavePoints(Array(60).fill(0).map((_, i) => 
          Math.sin(i * 0.2 + Date.now() * 0.01) * 35 + Math.random() * 25
        ));
        setInnerWavePoints(Array(40).fill(0).map((_, i) => 
          Math.cos(i * 0.3 + Date.now() * 0.015) * 25 + Math.random() * 20
        ));
        // Simulated voice spectrum (more mid/high energy)
        setSpectrum(Array(24).fill(0).map((_, i) => {
          const band = i / 24;
          const midBoost = Math.exp(-Math.pow((band - 0.6) / 0.25, 2));
          return Math.min(100, (Math.random() * 40 + 60 * midBoost));
        }));
      } else if (status === 'thinking') {
        // Thinking pattern - slower pulsing
        setFrequencyBars(Array(40).fill(0).map(() => Math.random() * 50 + 10));
        setWavePoints(Array(60).fill(0).map((_, i) =>
          Math.sin(i * 0.12 + Date.now() * 0.006) * 25
        ));
        setInnerWavePoints(Array(40).fill(0).map((_, i) =>
          Math.cos(i * 0.18 + Date.now() * 0.008) * 18
        ));
        // brainwave-like slow spectrum ripples
        setSpectrum(Array(24).fill(0).map((_, i) => {
          const band = i / 24;
          return 20 + 25 * Math.sin(Date.now() * 0.001 + band * 4);
        }));
      } else if (status === 'listening') {
        // Listening pattern - responsive but calmer
        setFrequencyBars(Array(40).fill(0).map(() => Math.random() * 70 + 20));
        setWavePoints(Array(60).fill(0).map((_, i) => 
          Math.sin(i * 0.15 + Date.now() * 0.008) * 30
        ));
        setInnerWavePoints(Array(40).fill(0).map((_, i) => 
          Math.cos(i * 0.2 + Date.now() * 0.01) * 20
        ));
        // Simulated incoming audio spectrum, more highs
        setSpectrum(Array(24).fill(0).map((_, i) => {
          const band = i / 24;
          const highBoost = Math.exp(-Math.pow((band - 0.8) / 0.2, 2));
          return Math.min(90, (Math.random() * 35 + 50 * highBoost));
        }));
      } else {
        // Idle pattern - breathing, subtle
        setFrequencyBars(Array(40).fill(0).map((_, i) => 
          Math.sin(i * 0.5 + Date.now() * 0.003) * 25 + 20
        ));
        setWavePoints(Array(60).fill(0).map((_, i) => 
          Math.sin(i * 0.1 + Date.now() * 0.005) * 20
        ));
        setInnerWavePoints(Array(40).fill(0).map((_, i) => 
          Math.cos(i * 0.15 + Date.now() * 0.006) * 15
        ));
        setSpectrum(Array(24).fill(0).map(() => 10 + Math.random() * 10));
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
          primary: '#FF1E8E', // Hot pink
          secondary: '#00FFD1', // Bright cyan
          tertiary: '#00FF88', // Neon green
          glow: 'rgba(255, 30, 142, 0.6)'
        };
      case 'thinking':
        return {
          primary: '#FFA500', // Orange
          secondary: '#FFC857', // Light amber
          tertiary: '#FFD27F',
          glow: 'rgba(255, 168, 76, 0.6)'
        };
      case 'listening':
        return {
          primary: '#00FFD1', // Bright cyan
          secondary: '#00FF88', // Neon green
          tertiary: '#00E5CC', // Turquoise
          glow: 'rgba(0, 255, 209, 0.6)'
        };
      default:
        return {
          primary: '#00E5CC', // Turquoise
          secondary: '#00FFD1', // Cyan
          tertiary: '#00D9FF', // Sky cyan
          glow: 'rgba(0, 229, 204, 0.5)'
        };
    }
  };

  const colors = getColorScheme();
  const centerX = 150;
  const centerY = 150;
  const baseRadius = 50;

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
    <div className="border-2 border-cyan-400/60 bg-gradient-to-br from-slate-900/80 to-cyan-950/60 backdrop-blur-sm p-6 relative overflow-hidden aspect-square shadow-2xl shadow-cyan-400/30">
      {/* Spectrum bars (bottom) */}
      {isAwake && (
        <div className="absolute bottom-4 left-4 right-4 h-10 flex items-end gap-1 opacity-80">
          {spectrum.map((v, i) => (
            <motion.div
              key={`spec-${i}`}
              className="flex-1 rounded-sm"
              style={{ background: colors.secondary }}
              animate={{ height: `${Math.max(4, v)}%`, opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.01 }}
            />
          ))}
        </div>
      )}
      {/* Glow effect */}
      {isAwake && (
        <motion.div
          className="absolute inset-0 blur-3xl"
          style={{ background: colors.glow }}
          animate={{
            opacity: [0.4, 0.7, 0.4],
            scale: [0.8, 1.1, 0.8]
          }}
          transition={{ duration: 3, repeat: Infinity }}
        />
      )}

      <div className="relative w-full h-full flex items-center justify-center">
        <svg width="300" height="300" viewBox="0 0 300 300" className="absolute">
          {/* Outer frequency ring - like audio visualizer */}
          {isAwake && frequencyBars.map((height, i) => {
            const angle = (i * 360) / frequencyBars.length;
            const innerRadius = 115;
            const outerRadius = 115 + (height * 0.5);
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
                strokeWidth="3"
                strokeLinecap="round"
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 0.4, delay: i * 0.005, repeat: Infinity }}
                filter="url(#glow)"
              />
            );
          })}

          {/* Outer wave form - bright and vibrant */}
          {isAwake && (
            <motion.path
              d={generateWavePath(wavePoints, 95, 1)}
              fill="none"
              stroke={colors.secondary}
              strokeWidth="3"
              initial={{ pathLength: 0 }}
              animate={{ 
                pathLength: 1,
                opacity: [0.7, 1, 0.7]
              }}
              transition={{ 
                pathLength: { duration: 2 },
                opacity: { duration: 2, repeat: Infinity }
              }}
              filter="url(#glow)"
            />
          )}

          {/* Middle wave form */}
          {isAwake && (
            <motion.path
              d={generateWavePath(innerWavePoints, 70, 0.8)}
              fill="none"
              stroke={colors.tertiary}
              strokeWidth="4"
              animate={{ 
                opacity: [0.6, 0.9, 0.6]
              }}
              transition={{ duration: 1.5, repeat: Infinity }}
              filter="url(#glow)"
            />
          )}

          {/* Inner flowing wave - filled when speaking */}
          {isAwake && status === 'speaking' && (
            <>
              <motion.path
                d={generateWavePath(innerWavePoints, 50, 1.2)}
                fill={colors.primary}
                opacity="0.4"
                animate={{ 
                  scale: [0.9, 1.1, 0.9]
                }}
                transition={{ duration: 0.8, repeat: Infinity }}
                style={{ transformOrigin: 'center' }}
                filter="url(#glow)"
              />
              <motion.path
                d={generateWavePath(innerWavePoints, 50, 1.2)}
                fill="none"
                stroke={colors.secondary}
                strokeWidth="2"
                animate={{ 
                  scale: [1, 1.15, 1]
                }}
                transition={{ duration: 0.8, repeat: Infinity }}
                style={{ transformOrigin: 'center' }}
              />
            </>
          )}

          {/* Core orb - bright and glowing */}
          <motion.circle
            cx={centerX}
            cy={centerY}
            r={baseRadius}
            fill={`url(#orbGradient-${status})`}
            animate={isAwake ? {
              r: status === 'speaking' ? [baseRadius, baseRadius + 8, baseRadius] : [baseRadius, baseRadius + 3, baseRadius],
            } : {}}
            transition={{ duration: status === 'speaking' ? 0.5 : 2, repeat: Infinity }}
            filter="url(#glow)"
          />

          {/* Inner glow - white center */}
          {isAwake && (
            <motion.circle
              cx={centerX}
              cy={centerY}
              r={baseRadius * 0.5}
              fill="rgba(255, 255, 255, 0.6)"
              animate={{
                opacity: [0.4, 0.7, 0.4],
                r: [baseRadius * 0.4, baseRadius * 0.6, baseRadius * 0.4]
              }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          )}

          {/* Rotating particles - bright dots */}
          {isAwake && [0, 1, 2, 3].map((ring) => (
            <g key={`ring-${ring}`}>
              {Array.from({ length: 12 }).map((_, i) => {
                const angle = (i * 360) / 12 + ring * 12;
                const radius = 80 + ring * 8;
                const particleColor = ring % 2 === 0 ? colors.primary : colors.secondary;
                return (
                  <motion.circle
                    key={`particle-${ring}-${i}`}
                    cx={centerX}
                    cy={centerY}
                    r="2.5"
                    fill={particleColor}
                    animate={{
                      cx: centerX + Math.cos((angle * Math.PI) / 180) * radius,
                      cy: centerY + Math.sin((angle * Math.PI) / 180) * radius,
                      opacity: [0.4, 1, 0.4],
                      r: [2, 3.5, 2]
                    }}
                    transition={{
                      cx: { duration: 4 + ring, repeat: Infinity, ease: 'linear' },
                      cy: { duration: 4 + ring, repeat: Infinity, ease: 'linear' },
                      opacity: { duration: 1.5, repeat: Infinity, delay: i * 0.08 },
                      r: { duration: 1.5, repeat: Infinity, delay: i * 0.08 }
                    }}
                    filter="url(#glow)"
                  />
                );
              })}
            </g>
          ))}

          {/* Gradient definitions */}
          <defs>
            {/* Glow filter */}
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>

            <radialGradient id="orbGradient-idle">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
              <stop offset="30%" stopColor="#00FFD1" />
              <stop offset="100%" stopColor="#00E5CC" />
            </radialGradient>
            <radialGradient id="orbGradient-speaking">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="30%" stopColor="#FF1E8E" />
              <stop offset="60%" stopColor="#00FFD1" />
              <stop offset="100%" stopColor="#00FF88" />
            </radialGradient>
            <radialGradient id="orbGradient-listening">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="40%" stopColor="#00FFD1" />
              <stop offset="100%" stopColor="#00FF88" />
            </radialGradient>
            <radialGradient id="orbGradient-thinking">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="40%" stopColor="#FFC857" />
              <stop offset="100%" stopColor="#FFA500" />
            </radialGradient>
          </defs>
        </svg>

        {/* Status label */}
        <div className="absolute bottom-4 left-0 right-0 text-center">
          <motion.div 
            className="text-xs"
            style={{ color: colors.secondary || '#00FFD1' }}
            animate={{ opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            NEURAL CORE
          </motion.div>
          <div className={`text-sm mt-1 ${
            !isAwake ? 'text-gray-500' :
            status === 'speaking' ? 'text-pink-400' :
            status === 'listening' ? 'text-cyan-300' :
            'text-emerald-300'
          }`} style={{
            textShadow: isAwake ? `0 0 10px ${
              status === 'speaking' ? '#FF1E8E' :
              status === 'listening' ? '#00FFD1' :
              '#00E5CC'
            }` : 'none'
          }}>
            {isAwake ? status.toUpperCase() : 'DORMANT'}
          </div>
        </div>
      </div>
    </div>
  );
}
