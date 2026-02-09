import { RefreshCw, Home, LogOut, Moon, Smile, ShoppingBag, AlertTriangle, Radio, CheckCircle } from 'lucide-react';
import { motion } from 'motion/react';
import { PhoenixState, PhoenixLogEntry } from '../api/client';

interface PhoenixPanelProps {
  state: PhoenixState | null | undefined;
  log: PhoenixLogEntry[];
  loading: boolean;
  error?: string | null;
  onHomeChange: (home: 'home' | 'away' | 'sleep') => void;
  onMoodChange: (label: string, intensity?: number) => void;
  onRefresh: () => void;
}

const moods = [
  { label: 'Low', intensity: 0.25, color: 'bg-amber-500/30 border-amber-400/40' },
  { label: 'Balanced', intensity: 0.5, color: 'bg-cyan-500/20 border-cyan-400/40' },
  { label: 'Flow', intensity: 0.8, color: 'bg-emerald-500/20 border-emerald-400/40' },
];

export function PhoenixPanel({ state, log, loading, error, onHomeChange, onMoodChange, onRefresh }: PhoenixPanelProps) {
  const bag = state?.bag_inventory || {};
  const missing = Object.keys(bag).filter((k) => bag[k] === false);
  const lastLog = Array.isArray(log) && log.length > 0 ? log[log.length - 1] : null;

  const HomeIcon = state?.home_state === 'home' ? Home : state?.home_state === 'sleep' ? Moon : LogOut;

  return (
    <div className="border border-cyan-500/30 bg-slate-900/60 backdrop-blur-sm p-4 shadow-lg shadow-cyan-500/10">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-cyan-300" />
          <span className="text-xs text-cyan-400">PHOENIX-15 LINK</span>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs flex items-center gap-1 border border-cyan-500/40 px-2 py-1 hover:bg-cyan-500/10"
          disabled={loading}
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="border border-cyan-500/20 p-3">
          <div className="flex items-center justify-between text-xs text-cyan-500">
            <span>HOME STATE</span>
            <HomeIcon className="w-4 h-4" />
          </div>
          <div className="text-xl mt-2 text-cyan-200">
            {state?.home_state || 'unknown'}
          </div>
          <div className="flex gap-2 mt-3">
            <Chip label="Home" active={state?.home_state === 'home'} onClick={() => onHomeChange('home')} />
            <Chip label="Away" active={state?.home_state === 'away'} onClick={() => onHomeChange('away')} />
            <Chip label="Sleep" active={state?.home_state === 'sleep'} onClick={() => onHomeChange('sleep')} />
          </div>
        </div>

        <div className="border border-cyan-500/20 p-3">
          <div className="flex items-center justify-between text-xs text-cyan-500">
            <span>MOOD</span>
            <Smile className="w-4 h-4" />
          </div>
          <div className="text-xl mt-2 text-cyan-200">
            {state?.mood?.label || 'Balanced'} <span className="text-sm text-cyan-500">{Math.round((state?.mood?.intensity ?? 0.5) * 100)}%</span>
          </div>
          <div className="flex gap-2 mt-3">
            {moods.map((m) => (
              <button
                key={m.label}
                onClick={() => onMoodChange(m.label, m.intensity)}
                className={`text-xs px-2 py-1 border ${m.color} transition-colors ${state?.mood?.label === m.label ? 'shadow-lg shadow-cyan-400/20' : 'hover:bg-cyan-500/10'}`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div className="border border-cyan-500/20 p-3">
          <div className="flex items-center justify-between text-xs text-cyan-500">
            <span>BAG STATUS</span>
            <ShoppingBag className="w-4 h-4" />
          </div>
          <div className={`text-xl mt-2 ${missing.length ? 'text-amber-300' : 'text-emerald-300'}`}>
            {missing.length ? `${missing.length} missing` : 'Ready'}
          </div>
          <div className="text-[11px] text-cyan-500 mt-1">
            {lastLog ? `Last check: ${lastLog.ts}` : 'No bag log yet'}
          </div>
          {missing.length > 0 && (
            <div className="mt-2 space-y-1">
              {missing.map((m) => (
                <div key={m} className="flex items-center gap-2 text-xs text-amber-200">
                  <AlertTriangle className="w-3 h-3" />
                  <span>{m}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-3 text-xs text-amber-300 flex items-center gap-2">
          <AlertTriangle className="w-3 h-3" />
          <span>{error}</span>
        </div>
      )}

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-cyan-500">
        <div>Last sync: {state?.last_sync || 'n/a'}</div>
        <div className="text-right flex items-center justify-end gap-1">
          <CheckCircle className="w-3 h-3 text-emerald-400" />
          <span>Notifications: {state?.notifications_allowed === false ? 'Off' : 'On'}</span>
        </div>
      </div>
    </div>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className={`px-2 py-1 border text-xs transition-colors ${active ? 'bg-cyan-500/20 border-cyan-400' : 'border-cyan-500/30 hover:bg-cyan-500/10'}`}
    >
      {label}
    </motion.button>
  );
}
