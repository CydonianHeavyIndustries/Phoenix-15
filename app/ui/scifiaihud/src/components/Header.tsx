import { motion } from 'motion/react';
import { Settings, Power, Wifi, Cpu, Mic, Monitor, Clock, Waves } from 'lucide-react';
import { useEffect, useState } from 'react';

interface HeaderProps {
  onSettingsClick: () => void;
  onOpenHub: () => void;
  isHushed: boolean;
  isAwake: boolean;
  isConnected: boolean;
  onPowerClick: () => void;
  micLevel: number;
  deskLevel: number;
}

export function Header({
  onSettingsClick,
  onOpenHub,
  isHushed,
  isAwake,
  isConnected,
  onPowerClick,
  micLevel,
  deskLevel,
}: HeaderProps) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const mood = isAwake ? (isHushed ? 'HUSHED' : 'ACTIVE') : 'DORMANT';
  const moodColor = isAwake ? (isHushed ? 'text-pink-400' : 'text-emerald-300') : 'text-gray-500';

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="border-2 border-cyan-400/60 bg-slate-900/80 backdrop-blur-sm p-4 relative overflow-hidden shadow-2xl shadow-cyan-400/30"
    >
      {/* Animated top line - bright cyan */}
      <motion.div
        className="absolute top-0 left-0 h-[3px] bg-gradient-to-r from-transparent via-cyan-300 to-transparent shadow-lg shadow-cyan-400/50"
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
            <Cpu className="w-8 h-8 text-cyan-300" style={{ filter: 'drop-shadow(0 0 8px rgba(0, 255, 209, 0.8))' }} />
          </motion.div>
          
          <div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-300" style={{ textShadow: '0 0 10px rgba(0, 255, 209, 0.6)' }}>BJORGSUN-26 SYSTEM</span>
              <motion.div
                className={`w-2 h-2 rounded-full ${isAwake ? 'bg-emerald-400' : 'bg-gray-500'} shadow-lg`}
                style={{ boxShadow: isAwake ? '0 0 10px rgba(0, 255, 136, 0.8)' : 'none' }}
                animate={{ opacity: isAwake ? [1, 0.3, 1] : 1 }}
                transition={{ duration: 2, repeat: Infinity }}
              ></motion.div>
            </div>
            <div className="text-xs text-cyan-400">v4.2.1 // OPERATIONAL</div>
          </div>

          {/* Status Labels */}
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">MOOD:</span>
              <span className={moodColor} style={{ 
                textShadow: isAwake ? `0 0 8px ${isHushed ? '#FF1E8E' : '#00FF88'}` : 'none' 
              }}>{mood}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">STATUS:</span>
              <span className="text-emerald-300" style={{ 
                textShadow: isAwake ? '0 0 8px rgba(0, 255, 136, 0.8)' : 'none' 
              }}>{isAwake ? 'ONLINE' : 'STANDBY'}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">ROUTE:</span>
              <span className="text-cyan-300">MAIN</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Live Meters */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-cyan-300" />
              <div className="w-20 h-2 bg-black border border-cyan-400/50 relative overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 shadow-lg"
                  style={{
                    width: `${micLevel.toFixed(0)}%`,
                    boxShadow: '0 0 10px rgba(0, 255, 209, 0.6)',
                  }}
                  transition={{ duration: 0.08 }}
                />
              </div>
              <span className="text-xs text-cyan-400">MIC</span>
            </div>
            <div className="flex items-center gap-2">
              <Monitor className="w-4 h-4 text-cyan-300" />
              <div className="w-20 h-2 bg-black border border-cyan-400/50 relative overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-cyan-400 to-blue-400 shadow-lg"
                  style={{
                    width: `${deskLevel.toFixed(0)}%`,
                    boxShadow: '0 0 10px rgba(0, 217, 255, 0.6)',
                  }}
                  transition={{ duration: 0.08 }}
                />
              </div>
              <span className="text-xs text-cyan-400">DESK</span>
            </div>
          </div>

          {/* Clock */}
          <div className="flex items-center gap-2 text-xs border-l-2 border-cyan-400/50 pl-4">
            <Clock className="w-4 h-4 text-cyan-300" />
            <span className="text-cyan-300 font-mono">{time.toLocaleTimeString()}</span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <Wifi className={`w-4 h-4 ${isConnected ? 'text-emerald-300' : 'text-gray-500'}`} style={{ filter: isConnected ? 'drop-shadow(0 0 6px rgba(0, 255, 136, 0.8))' : 'none' }} />
            <span className={isConnected ? 'text-emerald-300' : 'text-gray-500'}>{isConnected ? 'CONNECTED' : 'OFFLINE'}</span>
          </div>
          
          <button
            onClick={onOpenHub}
            className="p-2 border-2 border-cyan-400/50 hover:bg-cyan-400/20 hover:shadow-lg hover:shadow-cyan-400/30 transition-all"
          >
            <Waves className="w-5 h-5 text-cyan-300" />
          </button>

          <button
            onClick={onSettingsClick}
            className="p-2 border-2 border-cyan-400/50 hover:bg-cyan-400/20 hover:shadow-lg hover:shadow-cyan-400/30 transition-all"
          >
            <Settings className="w-5 h-5 text-cyan-300" />
          </button>

          <button onClick={onPowerClick} className="p-2 border-2 border-pink-500/50 hover:bg-pink-500/20 hover:shadow-lg hover:shadow-pink-500/30 transition-all">
            <Power className="w-5 h-5 text-pink-400" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}
