import { useState } from 'react';
import { analyzeAudio, addFrequencyEmotion, type AudioAnalysis } from '../api/client';

type OrbHue = 'neutral' | 'sad' | 'energize' | 'focus';

const bandToHue = (analysis?: AudioAnalysis): OrbHue => {
  if (!analysis) return 'neutral';
  const match = analysis.matched_emotions?.[0]?.emotion?.toLowerCase() || '';
  if (match.includes('sad') || match.includes('guilt') || match.includes('regret')) return 'sad';
  if (match.includes('energy') || match.includes('hype')) return 'energize';
  if (match.includes('focus') || match.includes('calm')) return 'focus';
  const top = analysis.peaks?.[0]?.hz || 0;
  if (top >= 120 && top <= 170) return 'sad';
  if (top >= 250 && top <= 450) return 'energize';
  return 'neutral';
};

const hueColors: Record<OrbHue, { primary: string; secondary: string; glow: string }> = {
  neutral: { primary: '#00E5CC', secondary: '#00FFD1', glow: 'rgba(0, 229, 204, 0.5)' },
  sad: { primary: '#5DA0FF', secondary: '#7DD3FC', glow: 'rgba(93, 160, 255, 0.45)' },
  energize: { primary: '#FF7B1E', secondary: '#FFC857', glow: 'rgba(255, 123, 30, 0.45)' },
  focus: { primary: '#8B5CF6', secondary: '#22D3EE', glow: 'rgba(139, 92, 246, 0.45)' },
};

function formatPeaks(analysis?: AudioAnalysis) {
  if (!analysis?.peaks) return '';
  return analysis.peaks
    .slice(0, 3)
    .map((p) => `${p.hz.toFixed(0)} Hz`)
    .join(' · ');
}

export function FrequencyOrb() {
  const [analysis, setAnalysis] = useState<AudioAnalysis | null>(null);
  const [uploading, setUploading] = useState(false);
  const [emotionHz, setEmotionHz] = useState('');
  const [emotionLabel, setEmotionLabel] = useState('');
  const hue = bandToHue(analysis || undefined);
  const colors = hueColors[hue];

  const handleFile = async (file?: File | null) => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await analyzeAudio(file);
      setAnalysis(res.analysis);
    } catch (err) {
      console.error(err);
      alert('Analysis failed');
    } finally {
      setUploading(false);
    }
  };

  const handleEmotionSave = async () => {
    const hz = parseFloat(emotionHz);
    if (!hz || !emotionLabel.trim()) {
      alert('Enter Hz and emotion');
      return;
    }
    try {
      await addFrequencyEmotion(hz, emotionLabel.trim());
      alert('Saved frequency emotion mapping');
    } catch (err) {
      console.error(err);
      alert('Save failed');
    }
  };

  const intensity = Math.min(
    1,
    (analysis?.band_energy?.reduce((a, b) => a + b.energy, 0) || 0) / 1e7
  );

  return (
    <div className="border-2 border-cyan-500/60 bg-slate-900/70 p-4 rounded-lg shadow-xl flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-cyan-200 uppercase tracking-widest">Frequency Orb</div>
          <div className="text-xs text-cyan-300/70">
            Upload a track, map peaks to emotions, and visualize the dominant bands.
          </div>
        </div>
        <label className="cursor-pointer text-xs px-3 py-1 border border-cyan-500/70 rounded bg-cyan-500/10 hover:bg-cyan-500/20">
          {uploading ? 'Analyzing...' : 'Import audio'}
          <input type="file" accept=".wav,.mp3,.flac,.ogg" className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} />
        </label>
      </div>

      {/* Orb */}
      <div className="relative w-full aspect-square rounded-xl overflow-hidden bg-gradient-to-br from-slate-950/80 to-slate-900/60">
        <div className="absolute inset-0 blur-3xl" style={{ background: colors.glow, opacity: 0.7 * (0.3 + intensity) }}></div>
        <div className="absolute inset-0 flex items-center justify-center">
          <svg width="320" height="320" viewBox="0 0 320 320">
            <defs>
              <radialGradient id="freq-orb-grad">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
                <stop offset="30%" stopColor={colors.primary} />
                <stop offset="100%" stopColor={colors.secondary} />
              </radialGradient>
              <filter id="freq-glow">
                <feGaussianBlur stdDeviation="6" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <circle cx="160" cy="160" r={70 + intensity * 30} fill="url(#freq-orb-grad)" filter="url(#freq-glow)" />
            <circle cx="160" cy="160" r={35 + intensity * 15} fill="rgba(255,255,255,0.6)" opacity={0.7} />
          </svg>
        </div>
        <div className="absolute bottom-3 left-0 right-0 text-center text-xs text-cyan-200">
          {analysis ? formatPeaks(analysis) : 'No analysis yet'}
        </div>
      </div>

      {/* Details */}
      {analysis && (
        <div className="grid grid-cols-2 gap-3 text-xs text-cyan-100">
          <div className="space-y-2">
            <div className="font-semibold text-cyan-200">Peaks</div>
            <ul className="space-y-1">
              {analysis.peaks.slice(0, 4).map((p, i) => (
                <li key={i} className="flex justify-between">
                  <span>{p.hz.toFixed(1)} Hz</span>
                  <span className="text-cyan-300/70">{p.amplitude.toFixed(0)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="font-semibold text-cyan-200">Matched emotions</div>
            <ul className="space-y-1">
              {(analysis.matched_emotions?.length ? analysis.matched_emotions : [{ hz: analysis.peaks?.[0]?.hz, emotion: 'unmapped' }]).map((m, i) => (
                <li key={i} className="flex justify-between">
                  <span>{m?.hz ? `${m.hz.toFixed(1)} Hz` : 'peak'}</span>
                  <span className="text-emerald-300/80">{m?.emotion || 'unmapped'}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Add mapping */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <input
          className="col-span-1 bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          placeholder="Hz (e.g., 141)"
          value={emotionHz}
          onChange={(e) => setEmotionHz(e.target.value)}
        />
        <input
          className="col-span-1 bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          placeholder="Emotion (e.g., sadness)"
          value={emotionLabel}
          onChange={(e) => setEmotionLabel(e.target.value)}
        />
        <button
          className="col-span-1 bg-cyan-600/70 hover:bg-cyan-500 text-white rounded px-2 py-1"
          onClick={handleEmotionSave}
        >
          Tag freq
        </button>
      </div>

      <div className="pt-2 text-[11px] text-cyan-200/70 border-t border-cyan-500/30">
        Tribute: Heinrich Rudolf Hertz (1857–1894), who proved electromagnetic waves and gave us the hertz (Hz).
      </div>
    </div>
  );
}
