import { useEffect, useRef, useState } from 'react';
import { colorizeAudio } from '../api/client';

type WaveType = OscillatorType;

type Layer = {
  id: string;
  freq: number;
  type: WaveType;
  gain: number;
  pan: number;
};

export function FrequencyLab() {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const layersRef = useRef<Map<string, { osc: OscillatorNode; gain: GainNode; pan?: StereoPannerNode }>>(new Map());
  const [leftFreq, setLeftFreq] = useState(314); // default PI-ish
  const [rightFreq, setRightFreq] = useState(621);
  const [wave, setWave] = useState<WaveType>('sine');
  const [volume, setVolume] = useState(0.3);
  const [isRunning, setIsRunning] = useState(false);
  const [colorizedUrl, setColorizedUrl] = useState<string | null>(null);
  const [colorizing, setColorizing] = useState(false);

  // Cymatic sandbox
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [cymaticHz, setCymaticHz] = useState(141);
  const [modeM, setModeM] = useState(4);
  const [modeN, setModeN] = useState(5);
  const [sweepStart, setSweepStart] = useState(15);
  const [sweepEnd, setSweepEnd] = useState(18711);
  const [sweepSeconds, setSweepSeconds] = useState(6);

  useEffect(() => {
    return () => stopAll();
  }, []);

  useEffect(() => {
    drawCymatic();
  }, [cymaticHz, modeM, modeN]);

  const ensureCtx = () => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext();
    }
    return audioCtxRef.current;
  };

  const startLayer = (layer: Layer) => {
    const ctx = ensureCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const pan = ctx.createStereoPanner();
    osc.type = layer.type;
    osc.frequency.value = layer.freq;
    gain.gain.value = layer.gain;
    pan.pan.value = layer.pan;
    osc.connect(gain).connect(pan).connect(ctx.destination);
    osc.start();
    layersRef.current.set(layer.id, { osc, gain, pan });
  };

  const stopAll = () => {
    layersRef.current.forEach(({ osc, gain, pan }) => {
      try {
        gain.gain.exponentialRampToValueAtTime(0.0001, ensureCtx().currentTime + 0.2);
        osc.stop(ensureCtx().currentTime + 0.3);
      } catch {}
      try {
        osc.disconnect();
        gain.disconnect();
        pan?.disconnect();
      } catch {}
    });
    layersRef.current.clear();
    setIsRunning(false);
  };

  const startPiStack = () => {
    stopAll();
    const baseVol = volume;
    const layers: Layer[] = [
      { id: 'bg-sine-141', freq: 141, type: 'sine', gain: baseVol * 0.5, pan: 0 },
      { id: 'kick-tri-3.141', freq: 3.141, type: 'triangle', gain: baseVol * 0.3, pan: 0 },
      { id: 'dtmf-1633', freq: 1633, type: 'square', gain: baseVol * 0.15, pan: 0.3 },
      { id: 'dtmf-941', freq: 941, type: 'square', gain: baseVol * 0.15, pan: -0.3 },
      { id: 'note-dsharp', freq: 311, type: 'sawtooth', gain: baseVol * 0.2, pan: 0 },
    ];
    layers.forEach(startLayer);
    setIsRunning(true);
  };

  const startBinaural = () => {
    stopAll();
    const baseVol = volume;
    const layers: Layer[] = [
      { id: 'left', freq: leftFreq, type: wave, gain: baseVol, pan: -1 },
      { id: 'right', freq: rightFreq, type: wave, gain: baseVol, pan: 1 },
    ];
    layers.forEach(startLayer);
    setIsRunning(true);
  };

  const drawCymatic = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = (canvas.width = canvas.clientWidth);
    const h = (canvas.height = canvas.clientHeight);
    const image = ctx.createImageData(w, h);
    const data = image.data;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const nx = (x / w) * Math.PI * modeM;
        const ny = (y / h) * Math.PI * modeN;
        const v = Math.sin(nx) * Math.sin(ny) + Math.sin((cymaticHz / 100) * nx);
        const intensity = Math.floor(Math.min(255, Math.abs(v) * 255));
        const idx = (y * w + x) * 4;
        data[idx] = intensity * 0.2;
        data[idx + 1] = intensity;
        data[idx + 2] = 180 + (intensity >> 2);
        data[idx + 3] = 255;
      }
    }
    ctx.putImageData(image, 0, 0);
  };

  const runSweep = () => {
    const ctx = ensureCtx();
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(sweepStart, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(sweepEnd, ctx.currentTime + sweepSeconds);
    gainNode.gain.setValueAtTime(volume, ctx.currentTime);
    osc.connect(gainNode).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + sweepSeconds);
    osc.onended = () => {
      try {
        osc.disconnect();
        gainNode.disconnect();
      } catch {}
    };
  };

  return (
    <div className="border border-cyan-600/60 rounded-lg p-4 bg-slate-900/70 shadow-lg space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-cyan-200 uppercase tracking-widest">Frequency Lab (Pi Stack)</div>
          <div className="text-xs text-cyan-300/70">Layer 141 Hz + 3.141 Hz + DTMF (1633/941) + D# ~311 Hz</div>
          <div className="text-[11px] text-amber-200/80 pt-1">
            Tribute: Heinrich Rudolf Hertz (1857–1894), father of the hertz (Hz).
            <span className="ml-2 text-cyan-200/80">Base “First Frequency”: 293 Hz.</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            className="px-3 py-1 rounded bg-blue-700 hover:bg-blue-600 text-white text-xs"
            onClick={() => {
              setLeftFreq(293);
              setRightFreq(293);
              setCymaticHz(293);
              startPiStack();
            }}
          >
            First Frequency
          </button>
          <button className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs" onClick={startPiStack}>
            Start Pi Stack
          </button>
          <button className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs" onClick={stopAll}>
            Stop All
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 text-xs">
        <div className="col-span-2">
          <label className="block text-cyan-200 mb-1">Left Ear (Hz)</label>
          <input
            type="number"
            min={15}
            max={18711}
            value={leftFreq}
            onChange={(e) => setLeftFreq(parseFloat(e.target.value) || 0)}
            className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-cyan-200 mb-1">Right Ear (Hz)</label>
          <input
            type="number"
            min={15}
            max={18711}
            value={rightFreq}
            onChange={(e) => setRightFreq(parseFloat(e.target.value) || 0)}
            className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-cyan-200 mb-1">Cymatic frequency (Hz)</label>
          <input
            type="number"
            min={15}
            max={18711}
            value={cymaticHz}
            onChange={(e) => setCymaticHz(parseFloat(e.target.value) || 0)}
            className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          />
        </div>
        <div>
          <label className="block text-cyan-200 mb-1">Mode m</label>
          <input
            type="number"
            min={1}
            max={12}
            value={modeM}
            onChange={(e) => setModeM(parseInt(e.target.value) || 1)}
            className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          />
        </div>
        <div>
          <label className="block text-cyan-200 mb-1">Mode n</label>
          <input
            type="number"
            min={1}
            max={12}
            value={modeN}
            onChange={(e) => setModeN(parseInt(e.target.value) || 1)}
            className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          />
        </div>
        <div>
          <label className="block text-cyan-200 mb-1">Wave</label>
          <select
            value={wave}
            onChange={(e) => setWave(e.target.value as WaveType)}
            className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
          >
            <option value="sine">Sine</option>
            <option value="triangle">Triangle</option>
            <option value="square">Square</option>
            <option value="sawtooth">Sawtooth</option>
          </select>
        </div>
        <div>
          <label className="block text-cyan-200 mb-1">Volume</label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            className="w-full"
          />
          <div className="text-cyan-300/70 text-[10px]">{Math.round(volume * 100)}%</div>
        </div>
        <div className="col-span-2 flex items-end gap-2">
          <button className="flex-1 px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white" onClick={startBinaural}>
            Play Binaural
          </button>
          <button className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white" onClick={stopAll}>
            Stop
          </button>
        </div>
        <div className="col-span-4 text-cyan-300/70 text-[11px]">
          Range: 15–18711 Hz. Pi stack layers: 141 Hz sine (bg), 3.141 Hz triangle (kick), DTMF 1633/941 Hz, D# ≈311 Hz.
        </div>
      </div>

      <div className="text-[11px] text-cyan-200/70">
        Status: {isRunning ? 'playing' : 'stopped'} · Left {leftFreq} Hz · Right {rightFreq} Hz · Wave {wave}
      </div>

      {/* Colorize voice: upload WAV, apply PI stack coloring */}
      <div className="mt-2 border border-cyan-500/30 rounded p-2 text-xs text-cyan-100 space-y-2">
        <div className="font-semibold text-cyan-200">Colorize WAV with PI tones</div>
        <div className="flex items-center gap-2">
          <label className="cursor-pointer px-3 py-1 rounded bg-cyan-600/70 hover:bg-cyan-500 text-white">
            {colorizing ? 'Processing...' : 'Upload WAV'}
            <input
              type="file"
              accept=".wav,.mp3,.flac,.ogg"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setColorizing(true);
                try {
                  const blob = await colorizeAudio(file, {
                    gain141: 0.1,
                    lfoHz: 3.141,
                    lfoDepth: 0.1,
                    partialGain: 0.05,
                  });
                  const url = URL.createObjectURL(blob);
                  setColorizedUrl(url);
                } catch (err) {
                  console.error(err);
                  alert('Colorize failed');
                } finally {
                  setColorizing(false);
                  e.target.value = '';
                }
              }}
            />
          </label>
          {colorizedUrl && (
            <audio controls src={colorizedUrl} className="flex-1">
              Your browser does not support audio.
            </audio>
          )}
        </div>
        <div className="text-cyan-300/70">
          Mixes 141 Hz bed + 3.141 Hz LFO tremolo + DTMF 1633/941 partials onto your WAV for the Bjorgsun hue.
        </div>
      </div>

      {/* Offline Cymatic sandbox */}
      <div className="mt-3 border border-cyan-500/40 rounded p-3 bg-slate-900/60">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-sm text-cyan-200 uppercase tracking-widest">Cymatic Sandbox</div>
            <div className="text-[11px] text-cyan-300/80">
              Visualize Chladni / cymatic patterns without AI — driven by your frequency, modes (m,n), or sweeps.
            </div>
          </div>
          <div className="flex gap-2">
            <button className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs" onClick={runSweep}>
              Sweep
            </button>
            <button className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs" onClick={stopAll}>
              Stop
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-[11px] text-cyan-200/80 mb-2">
          <label className="space-y-1">
            <span className="block">Sweep start (Hz)</span>
            <input
              type="number"
              min={15}
              max={18711}
              value={sweepStart}
              onChange={(e) => setSweepStart(parseFloat(e.target.value) || 15)}
              className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
            />
          </label>
          <label className="space-y-1">
            <span className="block">Sweep end (Hz)</span>
            <input
              type="number"
              min={15}
              max={18711}
              value={sweepEnd}
              onChange={(e) => setSweepEnd(parseFloat(e.target.value) || 18711)}
              className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
            />
          </label>
          <label className="space-y-1">
            <span className="block">Sweep duration (s)</span>
            <input
              type="number"
              min={1}
              max={30}
              value={sweepSeconds}
              onChange={(e) => setSweepSeconds(parseFloat(e.target.value) || 6)}
              className="w-full bg-slate-800/70 border border-cyan-500/40 rounded px-2 py-1 text-cyan-100"
            />
          </label>
          <div className="space-y-1 text-[10px] text-cyan-300/80">
            <div>Tribute: Heinrich Rudolf Hertz (1857–1894), father of the hertz (Hz).</div>
            <div>Use PI: 141 BPM base, 141 Hz carrier, 3.141 Hz modulation for visual experiments.</div>
          </div>
        </div>

        <canvas ref={canvasRef} className="w-full h-64 bg-black border border-cyan-500/30" />
      </div>
    </div>
  );
}
