import { useCoach } from '../hooks/useCoach';

function formatDuration(seconds?: number) {
  if (!seconds && seconds !== 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

export function CoachPanel() {
  const { telemetry, advice, botTuning, loading, error, refresh } = useCoach(10000);

  return (
    <div className="bg-gray-900/70 border border-cyan-500/30 rounded-xl p-4 shadow-lg shadow-cyan-500/10 backdrop-blur">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-cyan-300/70">TF2 AI Coach</p>
          <h3 className="text-lg font-semibold text-cyan-100">Live Insights</h3>
        </div>
        <button
          onClick={refresh}
          className="text-xs px-3 py-1 rounded-md bg-cyan-500/20 text-cyan-100 border border-cyan-400/30 hover:bg-cyan-500/30"
        >
          {loading ? 'Sync…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="text-pink-300 text-sm mb-3">
          Error: {error}
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 text-sm mb-4">
        <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
          <p className="text-cyan-300/70 text-xs">Map</p>
          <p className="text-cyan-100 font-semibold">{telemetry?.map || '—'}</p>
        </div>
        <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
          <p className="text-cyan-300/70 text-xs">Mode</p>
          <p className="text-cyan-100 font-semibold">{telemetry?.mode || '—'}</p>
        </div>
        <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
          <p className="text-cyan-300/70 text-xs">Duration</p>
          <p className="text-cyan-100 font-semibold">{formatDuration(telemetry?.duration)}</p>
        </div>
        <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
          <p className="text-cyan-300/70 text-xs">Elims</p>
          <p className="text-emerald-300 font-semibold text-lg">{telemetry?.elims ?? '—'}</p>
        </div>
        <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
          <p className="text-cyan-300/70 text-xs">Deaths</p>
          <p className="text-pink-300 font-semibold text-lg">{telemetry?.deaths ?? '—'}</p>
        </div>
        <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
          <p className="text-cyan-300/70 text-xs">E/D</p>
          <p className="text-cyan-100 font-semibold text-lg">
            {telemetry?.elims != null && telemetry?.deaths != null && telemetry.deaths !== 0
              ? (telemetry.elims / Math.max(1, telemetry.deaths)).toFixed(2)
              : '—'}
          </p>
        </div>
      </div>

      <div className="mb-4">
        <p className="text-cyan-300/70 text-xs mb-1">Advice</p>
        {advice.length === 0 && <p className="text-cyan-100 text-sm">No tips yet.</p>}
        <ul className="space-y-2">
          {advice.map((tip, idx) => (
            <li key={idx} className="text-cyan-100 text-sm bg-gray-800/60 border border-cyan-500/10 rounded-md p-2">
              • {tip}
            </li>
          ))}
        </ul>
      </div>

      {botTuning && (
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
            <p className="text-cyan-300/70 text-xs">Aggression</p>
            <p className="text-cyan-100 font-semibold">{botTuning.aggression ?? '—'}</p>
          </div>
          <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
            <p className="text-cyan-300/70 text-xs">Evasiveness</p>
            <p className="text-cyan-100 font-semibold">{botTuning.evasiveness ?? '—'}</p>
          </div>
          <div className="bg-gray-800/70 rounded-lg p-3 border border-cyan-500/10">
            <p className="text-cyan-300/70 text-xs">Range Pref</p>
            <p className="text-cyan-100 font-semibold">{botTuning.range_preference || '—'}</p>
          </div>
        </div>
      )}
    </div>
  );
}
