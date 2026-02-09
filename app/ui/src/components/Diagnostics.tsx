import { motion } from 'motion/react';
import { Activity, Cpu, HardDrive, Zap, Thermometer, MessageSquare, Volume2 } from 'lucide-react';

interface DiagnosticItem {
  label: string;
  value: number;
  unit: string;
  icon: React.ReactNode;
  color: string;
}

interface DiagnosticsProps {
  isAwake: boolean;
  metrics: {
    cpu: number;
    memory: number;
    power: number;
    temperature: number;
    gpu?: number;
    network?: string;
    discord?: boolean;
    tts?: boolean;
    processes?: number;
    uptime?: string;
  };
}

export function Diagnostics({ isAwake, metrics }: DiagnosticsProps) {
  const connectionStatus = {
    discord: !!metrics.discord,
    tts: !!metrics.tts,
  };

  const diagnostics: DiagnosticItem[] = [
    {
      label: 'CPU LOAD',
      value: metrics.cpu,
      unit: '%',
      icon: <Cpu className="w-4 h-4" />,
      color: 'cyan',
    },
    {
      label: 'MEMORY',
      value: metrics.memory,
      unit: '%',
      icon: <HardDrive className="w-4 h-4" />,
      color: 'cyan',
    },
    {
      label: 'GPU LOAD',
      value: metrics.power,
      unit: '%',
      icon: <Zap className="w-4 h-4" />,
      color: 'green',
    },
    {
      label: 'TEMP',
      value: metrics.temperature,
      unit: '°C',
      icon: <Thermometer className="w-4 h-4" />,
      color: 'yellow',
    },
  ];

  return (
    <div className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm relative overflow-hidden shadow-lg shadow-cyan-500/10">
      <div className="border-b border-cyan-500/30 p-3 flex items-center gap-2">
        <Activity className="w-5 h-5" />
        <span className="text-xs">SYSTEM DIAGNOSTICS</span>
      </div>

      <div className="p-4 space-y-4">
        {diagnostics.map((item, index) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="space-y-2"
          >
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                {item.icon}
                <span>{item.label}</span>
              </div>
              <span className={`text-${item.color}-400`}>
                {isAwake ? `${item.value}${item.unit}` : '--'}
              </span>
            </div>
            <div className="h-2 bg-black border border-cyan-500/20 relative overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-500/50 to-cyan-400"
                initial={{ width: 0 }}
                animate={{ width: isAwake ? `${item.value}%` : '0%' }}
                transition={{ duration: 0.5 }}
              />
              {isAwake && (
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                  animate={{ x: ['-100%', '100%'] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                  style={{ width: '30%' }}
                />
              )}
            </div>
          </motion.div>
        ))}

        <div className="pt-4 border-t border-cyan-500/20">
          <div className="text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-cyan-600">UPTIME</span>
              <span>{isAwake ? (metrics.uptime ?? '00:00:00') : '00:00:00'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-cyan-600">PROCESSES</span>
              <span>{isAwake ? (metrics.processes ?? 0) : '0'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-cyan-600">NETWORK</span>
              <span className={isAwake && connectionStatus.discord ? 'text-green-400' : 'text-gray-500'}>
                {isAwake ? (metrics.network ?? 'OFFLINE') : 'OFFLINE'}
              </span>
            </div>
          </div>
        </div>

        {/* Discord & TTS Status */}
        <div className="pt-4 border-t border-cyan-500/20 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs">
              <MessageSquare className="w-4 h-4" />
              <span className="text-cyan-600">DISCORD</span>
            </div>
            <motion.div
              className={`w-2 h-2 rounded-full ${connectionStatus.discord && isAwake ? 'bg-green-400' : 'bg-gray-500'}`}
              animate={connectionStatus.discord && isAwake ? { opacity: [1, 0.3, 1] } : {}}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs">
              <Volume2 className="w-4 h-4" />
              <span className="text-cyan-600">TTS ENGINE</span>
            </div>
            <motion.div
              className={`w-2 h-2 rounded-full ${connectionStatus.tts && isAwake ? 'bg-green-400' : 'bg-gray-500'}`}
              animate={connectionStatus.tts && isAwake ? { opacity: [1, 0.3, 1] } : {}}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
