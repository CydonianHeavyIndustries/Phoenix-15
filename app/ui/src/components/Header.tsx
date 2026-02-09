import { motion } from 'motion/react';
import { Settings, Power, Wifi, Cpu, Mic, Monitor, Clock } from 'lucide-react';
import { useEffect, useState } from 'react';

interface HeaderProps {
  onSettingsClick: () => void;
  isHushed: boolean;
  isAwake: boolean;
  micLevel?: number;
  deskLevel?: number;
  isConnected?: boolean;
  networkLabel?: string;
  onPower?: () => void;
}

export function Header({
  onSettingsClick,
  isHushed,
  isAwake,
  micLevel = 0,
  deskLevel = 0,
  isConnected = false,
  networkLabel = '',
  onPower
}: HeaderProps) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const mood = isAwake ? (isHushed ? 'HUSHED' : 'ACTIVE') : 'DORMANT';
  const moodColor = isAwake ? (isHushed ? 'text-magenta-400' : 'text-green-400') : 'text-gray-500';

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm p-4 relative overflow-hidden shadow-lg shadow-cyan-500/10"
    >
      {/* Animated top line */}
      <motion.div
        className="absolute top-0 left-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent"
        animate={{ x: ['-100%', '100%'] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        style={{ width: '50%' }}
      ></motion.div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <motion.div
            animate={{ rotate: isAwake ? 360 : 0 }}
            transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          >
            <Cpu className="w-8 h-8 text-cyan-400" />
          </motion.div>
          
          <div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">BJORGSUN-26</span>
              <motion.div
                className={`w-2 h-2 rounded-full ${isAwake ? 'bg-green-400' : 'bg-gray-500'}`}
                animate={{ opacity: isAwake ? [1, 0.3, 1] : 1 }}
                transition={{ duration: 2, repeat: Infinity }}
              ></motion.div>
            </div>
            <div className="text-xs text-cyan-600">v4.2.1 // OPERATIONAL</div>
          </div>

          {/* Status Labels */}
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-cyan-600">MOOD:</span>
              <span className={moodColor}>{mood}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-600">STATUS:</span>
              <span className="text-cyan-400">{isAwake ? 'ONLINE' : 'STANDBY'}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-600">ROUTE:</span>
              <span className="text-cyan-400">MAIN</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Live Meters */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-cyan-400" />
              <div className="w-20 h-2 bg-black border border-cyan-500/30 relative overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-cyan-500 to-green-400"
                  style={{ width: `${micLevel}%` }}
                  transition={{ duration: 0.1 }}
                />
              </div>
              <span className="text-xs text-cyan-600">MIC</span>
            </div>
            <div className="flex items-center gap-2">
              <Monitor className="w-4 h-4 text-cyan-400" />
              <div className="w-20 h-2 bg-black border border-cyan-500/30 relative overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-cyan-500 to-blue-400"
                  style={{ width: `${deskLevel}%` }}
                  transition={{ duration: 0.1 }}
                />
              </div>
              <span className="text-xs text-cyan-600">DESK</span>
            </div>
          </div>

          {/* Clock */}
          <div className="flex items-center gap-2 text-xs border-l border-cyan-500/30 pl-4">
            <Clock className="w-4 h-4 text-cyan-400" />
            <span className="text-cyan-400 font-mono">{time.toLocaleTimeString()}</span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <Wifi className={`w-4 h-4 ${isConnected ? 'text-green-400' : 'text-gray-500'}`} />
            <span className={isConnected ? 'text-cyan-400' : 'text-cyan-600'}>
              {isConnected ? (networkLabel || 'CONNECTED') : (networkLabel || 'OFFLINE')}
            </span>
          </div>
          
          <button
            onClick={onSettingsClick}
            className="p-2 border border-cyan-500/30 hover:bg-cyan-500/10 transition-colors"
          >
            <Settings className="w-5 h-5" />
          </button>
          
          <button
            onClick={onPower}
            className="p-2 border border-red-500/30 hover:bg-red-500/10 transition-colors"
          >
            <Power className="w-5 h-5 text-red-400" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}
