const BASE_URL = import.meta.env.VITE_API_BASE || 'http://localhost:1326';

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json();
}

async function apiPost<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return res.json();
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`UPLOAD ${path} -> ${res.status}`);
  return res.json();
}

export type PingResponse = {
  status: string;
  profile?: string;
  cpu_percent?: number;
  memory_percent?: number;
  voice_state?: any;
};

export type PhoenixState = {
  home_state: string;
  mood: { label: string; intensity: number };
  sleep_window?: { start: string; end: string };
  bag_inventory?: Record<string, boolean>;
  notifications_allowed?: boolean;
  last_sync?: string;
  updated?: boolean;
};

export type PhoenixLogEntry = {
  ts: string;
  missing: string[];
  location?: string;
};

export async function ping(): Promise<PingResponse> {
  return apiGet('/ping');
}

export async function wake() {
  return apiPost('/wake', {});
}

export async function selfCheck() {
  return apiPost('/selfcheck', {});
}

export async function powerOff() {
  return apiPost('/power', {});
}

export async function sleepSystem() {
  return apiPost('/sleep', {});
}

export async function getDevStatus() {
  return apiGet<{ ok: boolean; enabled: boolean }>('/devmode/status');
}

export async function enableDev(password: string) {
  return apiPost<{ ok: boolean; enabled: boolean }>('/devmode/enable', { password });
}

export async function getOllamaStatus() {
  return apiGet<{ ok: boolean }>('/ollama/status');
}

export async function startOllama() {
  return apiPost<{ ok: boolean }>('/ollama/start', {});
}

export async function importChatGPT(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/memory/import_chatgpt`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `UPLOAD /memory/import_chatgpt -> ${res.status}`);
  }
  return res.json();
}

export async function setRazerLighting(mode: 'dormant' | 'wake' | 'alert' | 'freq', opts?: { hz?: number; amp?: number; devices?: string[] }) {
  return apiPost('/razer/lighting', { mode, ...(opts || {}) });
}

export async function openLogs() {
  return apiGet('/logs/open');
}

export async function openFileBrowser(path?: string) {
  return apiPost('/files/open', { path });
}

export async function tailLogs(lines = 50): Promise<{ lines: string[] }> {
  return apiGet(`/logs/tail?lines=${lines}`);
}

export async function addMemory(text: string) {
  return apiPost('/memory/add', { text });
}

export async function memoryInfo() {
  return apiGet<{ ok?: boolean; size?: number; entries?: number; path?: string }>('/memory/info');
}

export async function memoryReload() {
  return apiPost<{ ok?: boolean; injected?: number; path?: string }>('/memory/reload', {});
}

export async function ttsEdge(text: string, voice = 'en-US-JennyNeural', pitch = '+4%', rate = '-2%') {
  const res = await fetch(`${BASE_URL}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, pitch, rate }),
  });
  if (!res.ok) throw new Error(`POST /tts -> ${res.status}`);
  const blob = await res.blob();
  return blob;
}

export async function listMemories() {
  return apiGet<any[]>('/memory/list');
}

export async function getCoach() {
  return apiGet('/tf2/coach/advice');
}

export async function sendTelemetry(payload: any) {
  return apiPost('/tf2/coach/telemetry', payload);
}

export async function chatLocal(message: string, history?: { role: string; content: string }[]) {
  return apiPost<{ ok: boolean; reply: string }>('/ai/local', { message, history });
}

// Phoenix-15 integration
export async function getPhoenixState(): Promise<{ ok: boolean; state: PhoenixState }> {
  return apiGet('/phoenix/state');
}

export async function setPhoenixHome(home_state: 'home' | 'away' | 'sleep') {
  return apiPost('/phoenix/home', { state: home_state });
}

export async function setPhoenixMood(label: string, intensity?: number) {
  return apiPost('/phoenix/mood', { label, intensity });
}

export async function updatePhoenixState(body: Partial<PhoenixState>) {
  const payload: any = {
    home_state: body.home_state,
    mood_label: body.mood?.label || (body as any).mood_label,
    mood_intensity: body.mood?.intensity ?? (body as any).mood_intensity,
    notifications_allowed: body.notifications_allowed,
    bag_inventory: body.bag_inventory,
  };
  return apiPost('/phoenix/state', payload);
}

export async function getPhoenixInventoryLog(lines = 30): Promise<{ ok: boolean; lines: PhoenixLogEntry[] }> {
  return apiGet(`/phoenix/inventory/log?lines=${lines}`);
}

// Audio frequency analysis
export type AudioAnalysis = {
  name: string;
  sr: number;
  duration_sec: number;
  centroid_hz: number;
  rolloff_hz: number;
  peaks: { hz: number; amplitude: number }[];
  band_energy: { label: string; lo: number; hi: number; energy: number }[];
  matched_emotions: { hz: number; emotion: string }[];
};

export async function analyzeAudio(file: File): Promise<{ ok: boolean; analysis: AudioAnalysis }> {
  return apiUpload('/audio/analyze', file);
}

export async function addFrequencyEmotion(hz: number, emotion: string) {
  return apiPost('/audio/emotion', { hz, emotion });
}

export async function colorizeAudio(file: File, params?: { gain141?: number; lfoHz?: number; lfoDepth?: number; partialGain?: number }) {
  const query = new URLSearchParams({
    gain_141: String(params?.gain141 ?? 0.1),
    lfo_hz: String(params?.lfoHz ?? 3.141),
    lfo_depth: String(params?.lfoDepth ?? 0.1),
    partial_gain: String(params?.partialGain ?? 0.05),
  });
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/audio/colorize?${query.toString()}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`UPLOAD /audio/colorize -> ${res.status}`);
  const blob = await res.blob();
  return blob;
}
