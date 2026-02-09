import { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { WakeStrip } from './components/WakeStrip';
import { ChatBox } from './components/ChatBox';
import { Diagnostics } from './components/Diagnostics';
import { Logs } from './components/Logs';
import { SettingsPanel } from './components/SettingsPanel';
import { OrbVisualizer } from './components/OrbVisualizer';
import { MoodCard } from './components/MoodCard';
import { SystemLog } from './components/SystemLog';
import { HushToggle } from './components/HushToggle';
import { LoginOverlay } from './components/LoginOverlay';
import { AlertToast } from './components/AlertToast';
import {
  apiAuth,
  apiWake,
  apiHush,
  apiSelfCheck,
  apiChat,
  apiLevels,
  apiDiagnostics,
  apiMood,
  apiLogs,
  apiTerminal,
  apiPower,
  apiOpenLogs,
} from './lib/api';

export default function App() {
  const [showSettings, setShowSettings] = useState(false);
  const [isAwake, setIsAwake] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isHushed, setIsHushed] = useState(false);
  const [systemStatus, setSystemStatus] = useState<'idle' | 'speaking' | 'listening'>('idle');
  const [alert, setAlert] = useState<{ type: 'error' | 'warning' | 'success'; message: string } | null>(null);
  const [metrics, setMetrics] = useState({
    cpu: 0,
    memory: 0,
    power: 0,
    temperature: 0,
    gpu: 0,
    network: 'OFFLINE',
    discord: false,
    tts: false,
    processes: 0,
    uptime: '0',
  });
  const [levels, setLevels] = useState({ mic: 0, desk: 0 });
  const [mood, setMood] = useState({ label: 'Neutral', tone: 'calm', intensity: 0.5 });
  const [logs, setLogs] = useState<string[]>([]);

  const handleWake = async () => {
    await apiWake();
    setIsAwake(true);
    setAlert({ type: 'success', message: 'Systems awakening...' });
    setTimeout(() => setAlert(null), 3000);
  };

  const handleSelfCheck = async () => {
    const res = await apiSelfCheck();
    if (res.items) {
      const lines = (res.items as any[]).map((it) => `${it[0] ? '[OK]' : '[WARN]'} ${it[1] || ''}`);
      setLogs((prev) => [...prev, ...lines].slice(-200));
    }
    setAlert({ type: res.ok ? 'success' : 'error', message: res.ok ? 'Self-check complete' : 'Self-check error' });
    setTimeout(() => setAlert(null), 3000);
  };

  const handleLogin = async (username: string, password: string) => {
    const res = await apiAuth(username, password);
    if (res.ok) {
      setIsLoggedIn(true);
      setIsAwake(false); // start offline until user presses Wake
      setLogs([]); // clear terminal/logs at session start
      setAlert({ type: 'success', message: 'Authenticated. Systems dormant until wake.' });
      setTimeout(() => setAlert(null), 2000);
    } else {
      setAlert({ type: 'error', message: 'Invalid credentials' });
      setTimeout(() => setAlert(null), 3000);
    }
  };

  // Poll diagnostics, levels, mood, logs
  useEffect(() => {
    const diagTimer = setInterval(async () => {
      try {
        const d = await apiDiagnostics();
        setMetrics({
          cpu: d.cpu ?? 0,
          memory: d.memory ?? 0,
          power: d.power ?? d.gpu ?? d.cpu ?? 0,
          temperature: d.temperature ?? 0,
          gpu: d.gpu ?? 0,
          network: d.network ?? 'OFFLINE',
          discord: !!d.discord,
          tts: !!d.tts,
          processes: d.processes ?? 0,
          uptime: d.uptime ?? '0',
        });
      } catch (_) {}
    }, 3000);

    const levelsTimer = setInterval(async () => {
      try {
        const l = await apiLevels();
        setLevels({ mic: Math.min(100, Math.max(0, (l.mic ?? 0) * 100)), desk: Math.min(100, Math.max(0, (l.desk ?? 0) * 100)) });
      } catch (_) {}
    }, 1200);

    const moodTimer = setInterval(async () => {
      try {
        const m = await apiMood();
        setMood({
          label: m.label ?? 'Neutral',
          tone: m.tone ?? 'calm',
          intensity: m.intensity ?? 0.5,
        });
      } catch (_) {}
    }, 5000);

    const logsTimer = setInterval(async () => {
      try {
        const res = await apiLogs();
        setLogs(res.lines ?? []);
      } catch (_) {}
    }, 4000);

    return () => {
      clearInterval(diagTimer);
      clearInterval(levelsTimer);
      clearInterval(moodTimer);
      clearInterval(logsTimer);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-teal-950 to-cyan-950 text-cyan-400 p-4 overflow-hidden relative">
      {/* Animated background particles */}
      <div className="fixed inset-0 opacity-20 pointer-events-none">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle, rgba(6, 182, 212, 0.1) 1px, transparent 1px)`,
          backgroundSize: '50px 50px'
        }}></div>
      </div>

      {/* Glowing orbs in background */}
      <div className="fixed top-20 left-20 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="fixed bottom-20 right-20 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none"></div>
      
      {/* Animated gradient overlay */}
      <div className="fixed inset-0 bg-gradient-to-br from-cyan-950/30 via-transparent to-teal-950/30 pointer-events-none"></div>

      <div className="relative z-10 max-w-[1800px] mx-auto">
        <Header 
          onSettingsClick={() => setShowSettings(!showSettings)}
          isHushed={isHushed}
          isAwake={isAwake}
          micLevel={levels.mic}
          deskLevel={levels.desk}
          isConnected={metrics.discord}
          networkLabel={metrics.network}
          onPower={async () => {
            const ok = window.confirm("Shutdown Bjorgsun now?");
            if (!ok) return;
            await apiPower();
            setAlert({ type: 'info', message: 'Power command sent' });
            setTimeout(() => setAlert(null), 2000);
          }}
        />
        
        <WakeStrip 
          isAwake={isAwake}
          onWake={handleWake}
          onSelfCheck={handleSelfCheck}
          onOpenLogs={async () => {
            try {
              await apiOpenLogs();
            } catch (_) {}
            try {
              const res = await apiLogs();
              setLogs(res.lines ?? []);
              setAlert({ type: 'info', message: 'Logs opened' });
              setTimeout(() => setAlert(null), 2000);
            } catch (_) {
              setAlert({ type: 'error', message: 'Open logs failed' });
              setTimeout(() => setAlert(null), 2000);
            }
          }}
        />
        
        <div className="grid grid-cols-12 gap-4 mt-4">
          {/* Left Panel - Chat */}
          <div className="col-span-12 lg:col-span-5">
            <ChatBox 
              isAwake={isAwake}
              onStatusChange={setSystemStatus}
              onSend={async (msg) => {
                const res = await apiChat(msg);
                return res.reply ?? '';
              }}
            />
          </div>

          {/* Right Panel - Visualizer, Mood, Diagnostics, Logs */}
          <div className="col-span-12 lg:col-span-7 space-y-4">
            {/* Orb and Mood Row */}
            <div className="grid grid-cols-2 gap-4">
              <OrbVisualizer status={systemStatus} isAwake={isAwake} />
              <MoodCard isAwake={isAwake} mood={mood} />
            </div>

            {/* Diagnostics and System Controls */}
            <div className="grid grid-cols-2 gap-4">
              <Diagnostics isAwake={isAwake} metrics={metrics} />
              <div className="space-y-4">
                <HushToggle
                  isHushed={isHushed}
                  onToggle={async (val) => {
                    setIsHushed(val);
                    await apiHush(val);
                  }}
                />
                <SystemLog logs={logs} onTerminal={apiTerminal} />
              </div>
            </div>

            {/* Logs */}
            <Logs logs={logs} />
          </div>
        </div>
      </div>

      {/* Settings Overlay */}
      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} />
      )}

      {/* Login Overlay */}
      {!isLoggedIn && (
        <LoginOverlay onLogin={handleLogin} />
      )}

      {/* Alert Toast */}
      {alert && (
        <AlertToast 
          type={alert.type}
          message={alert.message}
          onClose={() => setAlert(null)}
        />
      )}

      {/* Corner decorations */}
      <div className="fixed top-0 left-0 w-32 h-32 border-t-2 border-l-2 border-cyan-500 opacity-30 pointer-events-none"></div>
      <div className="fixed top-0 right-0 w-32 h-32 border-t-2 border-r-2 border-cyan-500 opacity-30 pointer-events-none"></div>
      <div className="fixed bottom-0 left-0 w-32 h-32 border-b-2 border-l-2 border-cyan-500 opacity-30 pointer-events-none"></div>
      <div className="fixed bottom-0 right-0 w-32 h-32 border-b-2 border-r-2 border-cyan-500 opacity-30 pointer-events-none"></div>
    </div>
  );
}
