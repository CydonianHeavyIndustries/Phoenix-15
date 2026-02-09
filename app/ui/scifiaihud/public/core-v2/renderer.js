const $ = (id) => document.getElementById(id);

const API_TIMEOUT_MS = 8000;
const API_LONG_TIMEOUT_MS = 30000;
const API_LLM_TIMEOUT_MS = 90000;
const MAX_ANIM_FPS = 60;
const MIN_ANIM_FRAME_MS = 1000 / MAX_ANIM_FPS;
let lastAnimFrameTs = 0;

function requestUiFrame(callback) {
  return requestAnimationFrame((ts) => {
    if (ts - lastAnimFrameTs < MIN_ANIM_FRAME_MS) {
      return requestAnimationFrame(callback);
    }
    lastAnimFrameTs = ts;
    callback(ts);
  });
}

function safeText(id, value) {
  const el = $(id);
  if (!el) {
    return false;
  }
  el.textContent = value;
  return true;
}

function on(id, event, handler) {
  const el = $(id);
  if (!el) {
    return false;
  }
  el.addEventListener(event, handler);
  return true;
}

function logUiError(message, detail) {
  try {
    reportIssue("PHX-UI-500", message || "ui_error", detail || "", {}, "error", false);
    fireAndForget(api.logClient?.(message, detail));
  } catch {
    // ignore
  }
}

function fireAndForget(promise) {
  if (!promise || typeof promise.catch !== "function") {
    return;
  }
  promise.catch(() => {});
}

let uiHeartbeatTimer = null;
const loopGuards = {};
function startUiHeartbeat() {
  if (uiHeartbeatTimer) {
    return;
  }
  uiHeartbeatTimer = setInterval(() => {
    try {
      fetch("/api/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ts: Date.now(),
          locked: state.locked,
          loading: state.loading,
        }),
      }).catch(() => {});
    } catch {
      // ignore
    }
  }, 2000);
}

function stopUiHeartbeat() {
  if (!uiHeartbeatTimer) {
    return;
  }
  clearInterval(uiHeartbeatTimer);
  uiHeartbeatTimer = null;
}

let orbBeatTimer = null;

function startOrbHeartbeatLoop() {
  if (orbBeatTimer) {
    return;
  }
  scheduleOrbBeat(true);
}

function stopOrbHeartbeatLoop() {
  if (!orbBeatTimer) {
    return;
  }
  clearTimeout(orbBeatTimer);
  orbBeatTimer = null;
}

function scheduleOrbBeat(initial = false) {
  if (!state.awake || state.orbState === "dormant") {
    stopOrbHeartbeatLoop();
    return;
  }
  const seconds = getHeartbeatSeconds();
  if (!Number.isFinite(seconds) || seconds <= 0) {
    stopOrbHeartbeatLoop();
    return;
  }
  const delayMs = Math.max(200, Math.round(seconds * 1000));
  if (initial) {
    orbBeatTimer = setTimeout(() => {
      onOrbBeat();
      scheduleOrbBeat(false);
    }, delayMs);
    return;
  }
  orbBeatTimer = setTimeout(() => {
    onOrbBeat();
    scheduleOrbBeat(false);
  }, delayMs);
}

function onOrbBeat() {
  state.orbBeatCounter += 1;
  maybeRequestOrbImage();
}

function shouldThrottleIssue(code, throttleMs = ISSUE_THROTTLE_MS) {
  const now = Date.now();
  const last = issueLastAt[code] || 0;
  if (throttleMs && now - last < throttleMs) {
    return true;
  }
  issueLastAt[code] = now;
  return false;
}

function reportIssue(code, message, detail, context = {}, severity = "error", throttle = true) {
  if (!code) {
    return;
  }
  if (throttle && shouldThrottleIssue(code)) {
    return;
  }
  const payload = {
    code,
    message: message || "",
    detail: detail || "",
    severity,
    source: "ui",
    context: context || {},
  };
  try {
    fireAndForget(api.logIssue?.(payload));
  } catch {
    // ignore
  }
  try {
    const summary = `${payload.message} ${payload.detail}`.trim();
    fireAndForget(api.logClient?.(`issue:${code}`, summary));
  } catch {
    // ignore
  }
}

function buildQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

function createWebApi() {
  const cfgBase = window.__BJ_CFG && window.__BJ_CFG.apiBase;
  let base = "";
  if (typeof cfgBase === "string") {
    const trimmed = cfgBase.trim();
    if (trimmed) {
      if (/^https?:\/\//i.test(trimmed)) {
        base = trimmed.replace(/\/$/, "");
      } else if (trimmed.startsWith("/")) {
        const origin = window.location && window.location.origin ? window.location.origin : "";
        if (origin && !origin.includes(":56795")) {
          base = origin + trimmed.replace(/\/$/, "");
        }
      }
    }
  }
  if (!base) {
    const origin = window.location && window.location.origin ? window.location.origin : "";
    base = origin && !origin.includes(":56795") ? origin : "http://127.0.0.1:1326";
  }

  function fetchWithTimeout(url, options = {}, timeoutMs = API_TIMEOUT_MS) {
    if (options.signal) {
      return fetch(url, options);
    }
    const controller = new AbortController();
    const timeout = Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : API_TIMEOUT_MS;
    const handle = setTimeout(() => controller.abort(), timeout);
    return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(handle));
  }

  async function request(path, options = {}, timeoutMs = API_TIMEOUT_MS) {
    const response = await fetchWithTimeout(
      `${base}${path}`,
      {
        headers: { "Content-Type": "application/json" },
        ...options,
      },
      timeoutMs
    );
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response.json();
  }

  async function requestBinary(path, payload, timeoutMs = API_LONG_TIMEOUT_MS) {
    const response = await fetchWithTimeout(
      `${base}${path}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      },
      timeoutMs
    );
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response.arrayBuffer();
  }

  async function requestForm(path, formData, timeoutMs = API_LONG_TIMEOUT_MS) {
    const response = await fetchWithTimeout(
      `${base}${path}`,
      {
        method: "POST",
        body: formData,
      },
      timeoutMs
    );
    if (!response.ok) {
      const message = await response.text();
      const error = new Error(message || `Request failed: ${response.status}`);
      error.status = response.status;
      error.url = `${base}${path}`;
      error.body = message;
      throw error;
    }
    return response.json();
  }

  return {
    baseUrl: base,
    ping: () => request("/ping"),
    wake: () => request("/wake", { method: "POST", body: "{}" }),
    sleep: () => request("/sleep", { method: "POST", body: "{}" }),
    reboot: () => request("/reboot", { method: "POST", body: "{}" }),
    selfcheck: (timeoutMs) =>
      request(
        "/selfcheck",
        { method: "POST", body: "{}" },
        Number.isFinite(timeoutMs) ? timeoutMs : API_LONG_TIMEOUT_MS
      ),
    logsOpen: () => request("/logs/open"),
    logsTail: (lines = 20) => request(`/logs/tail?lines=${lines}`),
    perfSnapshot: () => request("/perf"),
    filesOpen: (payload) =>
      request("/files/open", { method: "POST", body: JSON.stringify(payload || {}) }),
    usbDrives: () => request("/usb/drives"),
    usbOpen: (payload) =>
      request("/usb/open", { method: "POST", body: JSON.stringify(payload || {}) }),
    usbCopy: (payload) =>
      request("/usb/copy", { method: "POST", body: JSON.stringify(payload || {}) }),
    usbSyncStatus: () => request("/usb/sync/status"),
    usbSync: (payload) =>
      request("/usb/sync", { method: "POST", body: JSON.stringify(payload || {}) }),
    remoteStatus: () => request("/remote/status"),
    remoteTunnelStatus: () => request("/remote/tunnel/status"),
    remoteTunnelStart: () => request("/remote/tunnel/start", { method: "POST", body: "{}" }),
    remoteTunnelStop: () => request("/remote/tunnel/stop", { method: "POST", body: "{}" }),
    memoryInfo: () => request("/memory/info"),
    memoryCheck: () => request("/memory/check", { method: "POST", body: "{}" }),
    memoryReload: () => request("/memory/reload", { method: "POST", body: "{}" }),
    aiLocal: (payload) =>
      request(
        "/ai/local",
        { method: "POST", body: JSON.stringify(payload || {}) },
        API_LLM_TIMEOUT_MS
      ),
    orbImage: (payload) =>
      request(
        "/orb/image",
        { method: "POST", body: JSON.stringify(payload || {}) },
        API_LONG_TIMEOUT_MS
      ),
    visionAnalyze: (payload) =>
      request(
        "/vision/analyze",
        { method: "POST", body: JSON.stringify(payload || {}) },
        API_LONG_TIMEOUT_MS
      ),
    tts: (payload) => requestBinary("/tts", payload || {}, API_LONG_TIMEOUT_MS),
    settingsGet: (timeoutMs) => request("/settings/get", {}, timeoutMs),
    settingsSet: (payload) =>
      request("/settings/set", { method: "POST", body: JSON.stringify(payload || {}) }),
    systemMonitors: () => request("/system/monitors"),
    devAccessCheck: (key) =>
      request("/dev/access/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json", "dev-key": key },
        body: "{}",
      }),
    ollamaStatus: () => request("/ollama/status"),
    ollamaStart: () => request("/ollama/start", { method: "POST", body: "{}" }),
    audioHealth: () => request("/audio/api/health"),
    audioDevices: () => request("/audio/api/devices"),
    audioStatus: () => request("/audio/api/status"),
    audioActiveDevice: (payload) =>
      request("/audio/api/active-device", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioTone: (payload) =>
      request("/audio/api/tone", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioStop: () => request("/audio/api/stop", { method: "POST", body: "{}" }),
    audioSpectrum: () => request("/audio/api/spectrum"),
    audioEq: () => request("/audio/api/eq"),
    audioEqSet: (payload) =>
      request("/audio/api/eq", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioEqEngine: () => request("/audio/api/eq/engine"),
    audioEqApply: (payload) =>
      request("/audio/api/eq/apply", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioSettingsGet: (timeoutMs) => request("/audio/api/settings", {}, timeoutMs),
    audioSettingsSet: (payload) =>
      request("/audio/api/settings", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioProfiles: () => request("/audio/api/profiles"),
    audioProfileSave: (payload) =>
      request("/audio/api/profiles", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioProfileActive: () => request("/audio/api/profiles/active"),
    audioProfileApply: (payload) =>
      request("/audio/api/profiles/active", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioSystemMaster: (direction = "output") =>
      request(`/audio/api/system/master?direction=${direction}`),
    audioSystemMasterSet: (payload) =>
      request("/audio/api/system/master", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioSystemSessions: () => request("/audio/api/system/sessions"),
    audioSystemSessionSet: (payload) =>
      request("/audio/api/system/session", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioHearingTests: (params = {}) => request(`/audio/api/hearing/tests${buildQuery(params)}`),
    audioHearingTestAdd: (payload) =>
      request("/audio/api/hearing/tests", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioHearingSummary: (params = {}) => request(`/audio/api/hearing/summary${buildQuery(params)}`),
    audioVoiceCalibrate: (payload) =>
      request("/audio/api/voice/calibrate", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioVoiceRepeat: (payload) =>
      request("/audio/api/voice/repeat", { method: "POST", body: JSON.stringify(payload || {}) }),
    audioAnalyze: (formData) => requestForm("/frequency/analyze", formData, API_LONG_TIMEOUT_MS),
    audioEmotionTag: (payload) =>
      request("/frequency/emotion", { method: "POST", body: JSON.stringify(payload || {}) }),
    spotifyAuth: () => request("/spotify/auth"),
    spotifyStatus: () => request("/spotify/status"),
    spotifyDisconnect: () => request("/spotify/disconnect", { method: "POST", body: "{}" }),
    spotifyDevices: () => request("/spotify/devices"),
    spotifyTransfer: (payload) =>
      request("/spotify/transfer", { method: "POST", body: JSON.stringify(payload || {}) }),
    spotifyPlay: (payload) =>
      request("/spotify/play", { method: "POST", body: JSON.stringify(payload || {}) }),
    spotifyPause: () => request("/spotify/pause", { method: "POST", body: "{}" }),
    spotifyNext: () => request("/spotify/next", { method: "POST", body: "{}" }),
    spotifyPrevious: () => request("/spotify/previous", { method: "POST", body: "{}" }),
    spotifyVolume: (payload) =>
      request("/spotify/volume", { method: "POST", body: JSON.stringify(payload || {}) }),
    spotifyShuffle: (payload) =>
      request("/spotify/shuffle", { method: "POST", body: JSON.stringify(payload || {}) }),
    spotifyRepeat: (payload) =>
      request("/spotify/repeat", { method: "POST", body: JSON.stringify(payload || {}) }),
    logClient: (message, detail) =>
      request("/log/client", { method: "POST", body: JSON.stringify({ message, detail }) }),
    logIssue: (payload) =>
      request("/log/issue", { method: "POST", body: JSON.stringify(payload || {}) }),
    perfLog: (payload) =>
      request("/log/perf", { method: "POST", body: JSON.stringify(payload || {}) }),
  };
}

const api = window.bjorgsunApi || createWebApi();

const DISPLAY_MODE = new URLSearchParams(window.location.search).get("display") || "main";
const DISPLAY_ROLE_KEY = "bjorgsun_v2_display_main";
const DISPLAY_ROLE_TTL_MS = 120000;
const DISPLAY_ID = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const USER_STORE_KEY = "bjorgsun_v2_users";
const SETTINGS_TAB_KEY = "bjorgsun_v2_settings_tab";
const LEGACY_SETTINGS_KEY = "bjorgsun_v2_settings";
const HISTORY_KEY_PREFIX = "bjorgsun_v2_history_";
const MAX_HISTORY = 120;
const MAX_HISTORY_BYTES = 300000;
const PANEL_GRID_SIZE = 24;
const FREQ_LOG_KEY = "bjorgsun_v2_freq_logs";
const ISSUE_THROTTLE_MS = 30000;
const issueLastAt = {};
const AUDIO_SETTINGS_KEY = "bjorgsun_audio_settings";
const AUDIO_PROFILE_PREFS_KEY = "bjorgsun_audio_profile_prefs_";
const ORB_EMOTION_KEY_PREFIX = "bjorgsun_v2_orb_emotions_";
const AUDIO_EXAM_KEY = "bjorgsun_audio_exam_";
const AUDIO_SETTING_KEYS = [
  "systemSounds",
  "voiceFeedback",
  "replyChime",
  "volume",
  "chimeVolume",
  "hush",
  "systemAlerts",
  "processWarnings",
  "updateNotices",
  "voice",
  "rate",
  "pitch",
  "eqApoConfigPath",
  "mediaSource",
  "spotifyUrl",
];
const EMOTION_PROMPT_COOLDOWN_MS = 45000;
const EMOTION_PROMPT_SNOOZE_MS = 8 * 60 * 1000;
const ORB_EMOTION_BANDS = [
  { id: "0-40", range: [0, 40], palette: "Blues" },
  { id: "41-90", range: [41, 90], palette: "viridis" },
  { id: "91-150", range: [91, 150], palette: "plasma" },
  { id: "151-220", range: [151, 220], palette: "inferno" },
  { id: "221-300", range: [221, 300], palette: "magma" },
  { id: "301-500", range: [301, 500], palette: "coolwarm" },
  { id: "501-9999", range: [501, 9999], palette: "rainbow" },
];
const AUDIO_SETTINGS_MAP = {
  systemSounds: "system_sounds",
  voiceFeedback: "voice_feedback",
  replyChime: "reply_chime",
  volume: "volume",
  chimeVolume: "chime_volume",
  hush: "hush",
  systemAlerts: "system_alerts",
  processWarnings: "process_warnings",
  updateNotices: "update_notices",
  voice: "voice",
  rate: "rate",
  pitch: "pitch",
  eqApoConfigPath: "eq_apo_config_path",
  mediaSource: "media_source",
  spotifyUrl: "spotify_url",
};

window.addEventListener("error", (event) => {
  logUiError("ui_error", event?.message || String(event));
});

window.addEventListener("unhandledrejection", (event) => {
  logUiError("ui_rejection", event?.reason?.message || String(event?.reason || event));
});

const audioDefaults = {
  systemSounds: true,
  voiceFeedback: true,
  replyChime: true,
  volume: 70,
  chimeVolume: 35,
  hush: false,
  systemAlerts: true,
  processWarnings: true,
  updateNotices: true,
  voice: "en-US-JennyNeural",
  rate: "-5%",
  pitch: "+2%",
  eqApoConfigPath: "",
  mediaSource: "spotify",
  spotifyUrl: "",
};

const audioProfileDefaults = {
  warmth: 0,
  clarity: 0,
  air: 0,
  bass: 0,
};

const AUDIO_HEARING_DEFAULT_BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
const SPEECH_TEST_PHRASES = [
  "blue sky",
  "silver arrow",
  "nine two five",
  "open the gate",
  "quiet river",
  "bright signal",
  "green sunrise",
  "steady cadence",
];

const defaults = {
  loginEnabled: true,
  loginUser: "Phoenix",
  loginPass: "12345",
  aiName: "Bjorgsun-26",
  showChat: true,
  showSystem: true,
  showFrequency: true,
  showOrbTools: true,
  showAudio: true,
  showPerf: false,
  emotionPromptEnabled: true,
  usbLocalBootEnabled: false,
  usbLocalBootPath: "",
  usbIncludeOs: false,
  usbIncludeApp: true,
  usbIncludeMemory: true,
  usbIncludeUserData: true,
  usbCopyPreset: "full",
  remoteUiEnabled: false,
  remoteUiHost: "CHII.inc",
  remoteTunnelEnabled: false,
  desktopViewEnabled: false,
  desktopViewMonitors: [],
  performanceFocusEnabled: true,
  panelPositions: {},
  theme: {
    bg: "#070c14",
    panel: "rgba(9, 22, 34, 0.86)",
    panelBorder: "rgba(66, 244, 255, 0.35)",
    accent: "#3ef2e0",
    accentStrong: "#1de8ff",
    accentSoft: "rgba(62, 242, 224, 0.25)",
    text: "#d9f7ff",
    muted: "rgba(217, 247, 255, 0.6)",
  },
};

const state = {
  awake: false,
  locked: false,
  autoPerfActive: false,
  uiInitialized: false,
  postLoginReady: false,
  uiHidden: false,
  localSettingsLoaded: false,
  perfStats: {
    loops: {},
    lastReport: "",
    orb: {
      avgFrameMs: 0,
      lastFrameMs: 0,
      frameCount: 0,
      fps: 0,
      dotCount: 0,
      glyphCount: 0,
    },
  },
  displayMode: DISPLAY_MODE,
  secondaryDisplay: DISPLAY_MODE !== "main",
  displayId: DISPLAY_ID,
  activeUserId: "",
  userStore: { users: [], activeId: "" },
  adminUnlocked: false,
  orbState: "dormant",
  orbThought: "idle",
  orbFrequencyHz: null,
  orbHeartbeatHz: null,
  orbEmotion: "Unknown",
  emotionMap: {},
  emotionPrompt: {
    open: false,
    hz: null,
    bucket: null,
    palette: "gray",
    bandRange: "",
    state: "",
    reason: "",
    context: "",
  },
  emotionPromptSnooze: {},
  emotionPromptLastAt: 0,
  lastEmotionBucket: null,
  visualization: null,
  lastVisualizationThought: "",
  vizReinforce: 0,
  lastLogLine: "",
  settings: { ...defaults },
  displayMonitors: [],
  remoteTunnel: { running: false, url: "" },
  audioSettings: { ...audioDefaults },
  audioEqTarget: "output",
  audioEq: { bands: [], input: [], output: [] },
  audioProfiles: [],
  audioProfileActive: "",
  audioSessions: [],
  audioMaster: { volume: 70, mute: false, available: false },
  audioProfilePrefs: { ...audioProfileDefaults },
  audioHearingTest: {
    active: false,
    index: 0,
    target: "output",
    frequencies: [],
    results: [],
  },
  audioSpeechTest: {
    active: false,
    index: 0,
    phrases: [],
    expected: "",
    similarity: 0,
  },
  audioExam: {
    active: false,
    stage: "",
    startedAt: 0,
  },
  audioSuggestedEqBase: { input: [], output: [] },
  audioSuggestedEq: { input: [], output: [] },
  audioVoiceMetrics: { rms: null, peak: null },
  audioProfileStatus: "",
  audioExamStatus: { completedAt: null, runCount: 0 },
  spotify: {
    authorized: false,
    devices: [],
    activeDeviceId: "",
    volume: 50,
    shuffle: false,
    repeat: "off",
    isPlaying: false,
    track: "",
    user: "",
  },
  spotifyDevicesAt: 0,
  history: [],
  historyDeferred: false,
  userSessionHydrated: false,
  lastUserAt: 0,
  lastAssistantAt: 0,
  lastProactiveAt: 0,
  minimal: false,
  orbEnergy: 0.2,
  orbEnergyTarget: 0.2,
  orbStateChangedAt: 0,
  orbAnimationStarted: false,
  activeModule: "core",
  audioDevicesLoaded: false,
  freqFile: null,
  freqAnalysis: null,
  freqAnalyzing: false,
  freqTagLastSaved: { hz: null, emotion: "" },
  orbAction: "",
  orbActionUntil: 0,
  orbOverride: null,
  orbOverrideUntil: 0,
  pendingImage: null,
  pendingImageLoading: false,
  chatBusy: false,
  queuedMessage: null,
  orbImageDataUrl: "",
  orbImageKey: "",
  orbImageEnabled: true,
  orbImageLastAt: 0,
  orbImageInFlight: false,
  orbBeatCounter: 0,
  layoutReady: false,
  loading: true,
  bootChecks: [],
  bootError: null,
  bootStatus: "",
  loopsStarted: false,
};

const prompts = new Map();
const USB_COPY_PRESETS = {
  full: { usbIncludeApp: true, usbIncludeMemory: true, usbIncludeUserData: true },
  "ai-memory": { usbIncludeApp: false, usbIncludeMemory: true, usbIncludeUserData: false },
  "user-data": { usbIncludeApp: false, usbIncludeMemory: false, usbIncludeUserData: true },
};

function resolveDisplayRole() {
  if (DISPLAY_MODE === "secondary") {
    state.secondaryDisplay = true;
    state.displayMode = "secondary";
    return;
  }
  const now = Date.now();
  let current = null;
  try {
    const raw = localStorage.getItem(DISPLAY_ROLE_KEY);
    if (raw) {
      current = JSON.parse(raw);
    }
  } catch {
    current = null;
  }
  const stale =
    !current ||
    !current.id ||
    !Number.isFinite(current.ts) ||
    now - Number(current.ts) > DISPLAY_ROLE_TTL_MS;
  if (stale) {
    try {
      localStorage.setItem(
        DISPLAY_ROLE_KEY,
        JSON.stringify({ id: state.displayId, ts: now })
      );
    } catch {
      // ignore
    }
    state.secondaryDisplay = false;
    state.displayMode = "main";
    return;
  }
  if (current.id === state.displayId) {
    state.secondaryDisplay = false;
    state.displayMode = "main";
    return;
  }
  state.secondaryDisplay = true;
  state.displayMode = "secondary";
}

function refreshDisplayLease() {
  if (state.secondaryDisplay) {
    return;
  }
  try {
    localStorage.setItem(
      DISPLAY_ROLE_KEY,
      JSON.stringify({ id: state.displayId, ts: Date.now() })
    );
  } catch {
    // ignore
  }
}

function buildUserId(name) {
  const base = String(name || "user")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const suffix = Date.now().toString(36).slice(-4);
  return base ? `${base}-${suffix}` : `user-${suffix}`;
}

function clampNumber(value, minValue, maxValue, fallback) {
  const num = Number(value);
  if (Number.isNaN(num)) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, num));
}

function shuffleList(list) {
  const copy = Array.isArray(list) ? list.slice() : [];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function stripAudioKeys(settings) {
  const cleaned = { ...(settings || {}) };
  AUDIO_SETTING_KEYS.forEach((key) => {
    delete cleaned[key];
  });
  return cleaned;
}

function normalizeUserSettings(settings) {
  const merged = { ...defaults, ...stripAudioKeys(settings || {}) };
  merged.loginUser = String(merged.loginUser || defaults.loginUser || "User").trim();
  merged.loginPass = String(merged.loginPass || defaults.loginPass || "");
  merged.aiName = String(merged.aiName || defaults.aiName || "Bjorgsun-26").trim();
  merged.panelPositions =
    merged.panelPositions && typeof merged.panelPositions === "object"
      ? merged.panelPositions
      : {};
  merged.theme = normalizeTheme(merged.theme);
  return merged;
}

function normalizeAudioSettings(settings) {
  const merged = { ...audioDefaults, ...(settings || {}) };
  merged.volume = Math.round(clampNumber(merged.volume, 0, 100, audioDefaults.volume));
  merged.chimeVolume = Math.round(
    clampNumber(merged.chimeVolume, 0, 100, audioDefaults.chimeVolume)
  );
  merged.systemSounds = Boolean(merged.systemSounds);
  merged.voiceFeedback = Boolean(merged.voiceFeedback);
  merged.replyChime = Boolean(merged.replyChime);
  merged.hush = Boolean(merged.hush);
  merged.systemAlerts = Boolean(merged.systemAlerts);
  merged.processWarnings = Boolean(merged.processWarnings);
  merged.updateNotices = Boolean(merged.updateNotices);
  merged.voice = String(merged.voice || audioDefaults.voice).trim() || audioDefaults.voice;
  merged.rate = String(merged.rate || audioDefaults.rate).trim() || audioDefaults.rate;
  merged.pitch = String(merged.pitch || audioDefaults.pitch).trim() || audioDefaults.pitch;
  merged.eqApoConfigPath = String(
    merged.eqApoConfigPath || audioDefaults.eqApoConfigPath
  ).trim();
  merged.spotifyUrl = String(merged.spotifyUrl || audioDefaults.spotifyUrl).trim();
  const mediaSource = String(merged.mediaSource || audioDefaults.mediaSource).trim().toLowerCase();
  merged.mediaSource = ["spotify", "none"].includes(mediaSource)
    ? mediaSource
    : audioDefaults.mediaSource;
  return merged;
}

function normalizeAudioProfilePrefs(prefs) {
  const merged = { ...audioProfileDefaults, ...(prefs || {}) };
  Object.keys(audioProfileDefaults).forEach((key) => {
    merged[key] = clampNumber(merged[key], -10, 10, audioProfileDefaults[key]);
  });
  return merged;
}

function audioProfilePrefsKey(userId) {
  return `${AUDIO_PROFILE_PREFS_KEY}${userId || "default"}`;
}

function loadAudioProfilePrefs(userId) {
  if (!userId) {
    return { ...audioProfileDefaults };
  }
  try {
    const raw = localStorage.getItem(audioProfilePrefsKey(userId));
    if (raw) {
      return normalizeAudioProfilePrefs(JSON.parse(raw));
    }
  } catch {
    // ignore
  }
  return { ...audioProfileDefaults };
}

function orbEmotionKey(userId) {
  return `${ORB_EMOTION_KEY_PREFIX}${userId || "default"}`;
}

function loadOrbEmotionMap(userId) {
  if (!userId) {
    return {};
  }
  try {
    const raw = localStorage.getItem(orbEmotionKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return parsed;
      }
    }
  } catch {
    // ignore
  }
  return {};
}

function saveOrbEmotionMap(userId, map) {
  if (!userId) {
    return;
  }
  try {
    localStorage.setItem(orbEmotionKey(userId), JSON.stringify(map || {}));
  } catch {
    // ignore
  }
}

function saveAudioProfilePrefs(userId) {
  if (!userId) {
    return;
  }
  try {
    localStorage.setItem(
      audioProfilePrefsKey(userId),
      JSON.stringify(normalizeAudioProfilePrefs(state.audioProfilePrefs))
    );
  } catch {
    // ignore
  }
}

function audioExamKey(userId) {
  return `${AUDIO_EXAM_KEY}${userId || "default"}`;
}

function loadAudioExamStatus(userId) {
  if (!userId) {
    return { completedAt: null, runCount: 0 };
  }
  try {
    const raw = localStorage.getItem(audioExamKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        completedAt: typeof parsed.completedAt === "number" ? parsed.completedAt : null,
        runCount: clampNumber(parsed.runCount, 0, 999, 0),
      };
    }
  } catch {
    // ignore
  }
  return { completedAt: null, runCount: 0 };
}

function saveAudioExamStatus(userId) {
  if (!userId) {
    return;
  }
  try {
    localStorage.setItem(
      audioExamKey(userId),
      JSON.stringify({
        completedAt: state.audioExamStatus.completedAt,
        runCount: state.audioExamStatus.runCount || 0,
      })
    );
  } catch {
    // ignore
  }
}

function formatExamTimestamp(value) {
  if (!value) {
    return "";
  }
  try {
    const date = new Date(value);
    return date.toLocaleString();
  } catch {
    return "";
  }
}

function pickAudioKeys(settings) {
  const picked = {};
  AUDIO_SETTING_KEYS.forEach((key) => {
    if (settings && settings[key] !== undefined) {
      picked[key] = settings[key];
    }
  });
  return picked;
}

function audioSettingsToApi(settings) {
  const payload = {};
  Object.entries(AUDIO_SETTINGS_MAP).forEach(([localKey, apiKey]) => {
    if (settings[localKey] !== undefined) {
      payload[apiKey] = settings[localKey];
    }
  });
  return payload;
}

function audioSettingsFromApi(settings) {
  const mapped = {};
  Object.entries(AUDIO_SETTINGS_MAP).forEach(([localKey, apiKey]) => {
    if (settings && settings[apiKey] !== undefined) {
      mapped[localKey] = settings[apiKey];
    }
  });
  return mapped;
}

function loadLegacyAudioSettings() {
  let legacy = {};
  let store = {};
  try {
    const legacyRaw = localStorage.getItem(LEGACY_SETTINGS_KEY);
    if (legacyRaw) {
      legacy = JSON.parse(legacyRaw);
    }
  } catch {
    legacy = {};
  }
  try {
    const storeRaw = localStorage.getItem(USER_STORE_KEY);
    if (storeRaw) {
      store = JSON.parse(storeRaw);
    }
  } catch {
    store = {};
  }
  let userSettings = {};
  const users = Array.isArray(store.users) ? store.users : [];
  const active = users.find((user) => user.id === store.activeId) || users[0];
  if (active && active.settings) {
    userSettings = active.settings;
  }
  return { ...pickAudioKeys(legacy), ...pickAudioKeys(userSettings) };
}

function saveAudioSettingsLocal() {
  try {
    localStorage.setItem(AUDIO_SETTINGS_KEY, JSON.stringify(state.audioSettings));
  } catch {
    // ignore
  }
}

function saveAudioSettings() {
  state.audioSettings = normalizeAudioSettings(state.audioSettings);
  saveAudioSettingsLocal();
  api.audioSettingsSet(audioSettingsToApi(state.audioSettings)).catch(() => {});
}

async function waitForAudioHealth(maxWaitMs = 30000) {
  const deadline = Date.now() + Math.max(0, Number(maxWaitMs) || 0);
  while (Date.now() < deadline) {
    try {
      await withTimeout(api.audioHealth(), 4000, "audio health timeout");
      return true;
    } catch {
      // ignore
    }
    await delay(1000);
  }
  return false;
}

function loadAudioSettings(options = {}) {
  let local = {};
  try {
    const raw = localStorage.getItem(AUDIO_SETTINGS_KEY);
    if (raw) {
      local = JSON.parse(raw);
    }
  } catch {
    local = {};
  }
  if (!local || Object.keys(local).length === 0) {
    local = loadLegacyAudioSettings();
  }
  state.audioSettings = normalizeAudioSettings({ ...state.audioSettings, ...local });
  const timeoutMs =
    options && Number.isFinite(options.timeoutMs) ? Number(options.timeoutMs) : undefined;
  return api
    .audioSettingsGet(timeoutMs)
    .then((data) => {
      const remote = audioSettingsFromApi(data && data.settings ? data.settings : {});
      if (Object.keys(remote).length > 0) {
        state.audioSettings = normalizeAudioSettings({ ...state.audioSettings, ...remote });
        saveAudioSettingsLocal();
      }
      return true;
    })
    .catch((err) => {
      if (options && options.throwOnFailure) {
        throw err;
      }
      return false;
    });
}

function loadUserStore() {
  const store = { users: [], activeId: "" };
  let loaded = false;
  try {
    const raw = localStorage.getItem(USER_STORE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.users)) {
        store.users = parsed.users;
        store.activeId = parsed.activeId || "";
        loaded = true;
      }
    }
  } catch (error) {
    // ignore corrupt store
  }
  if (!Array.isArray(store.users)) {
    store.users = [];
  }
  if (store.users.length === 0) {
    let legacySettings = {};
    try {
      const legacyRaw = localStorage.getItem(LEGACY_SETTINGS_KEY);
      if (legacyRaw) {
        legacySettings = JSON.parse(legacyRaw);
      }
    } catch (error) {
      legacySettings = {};
    }
    const settings = normalizeUserSettings(legacySettings);
    const userId = "phoenix";
    store.users = [{ id: userId, settings, createdAt: new Date().toISOString() }];
    store.activeId = userId;
  }
  store.users = store.users.map((user, idx) => {
    const normalized = { ...user };
    if (!normalized.id) {
      normalized.id = `user-${idx + 1}`;
    }
    normalized.settings = normalizeUserSettings(normalized.settings || {});
    return normalized;
  });
  if (!store.activeId || !store.users.find((user) => user.id === store.activeId)) {
    store.activeId = store.users[0]?.id || "";
  }
  return { store, loaded };
}

function saveUserStore() {
  try {
    localStorage.setItem(
      USER_STORE_KEY,
      JSON.stringify({ users: state.userStore.users, activeId: state.activeUserId })
    );
  } catch (error) {
    // ignore
  }
}

function getActiveUser() {
  return state.userStore.users.find((user) => user.id === state.activeUserId) || null;
}

function persistActiveUser() {
  const user = getActiveUser();
  if (!user) {
    return;
  }
  user.settings = { ...state.settings };
  saveUserStore();
}

function applyBranding() {
  const aiName = (state.settings.aiName || defaults.aiName || "").trim();
  safeText("brand-ai", aiName ? `AI: ${aiName}` : "");
  safeText("login-ai-label", aiName ? `AI: ${aiName}` : "");
  safeText("orb-sub", aiName || "NEURAL CORE");
  if (aiName) {
    document.title = `${aiName} Core v2`;
  }
}

function syncUserSelects() {
  const selects = [$("setting-active-user"), $("login-user-select")];
  const activeId = state.activeUserId;
  selects.forEach((select) => {
    if (!select) {
      return;
    }
    select.innerHTML = "";
    state.userStore.users.forEach((user) => {
      const opt = document.createElement("option");
      opt.value = user.id;
      opt.textContent = user.settings?.loginUser || "User";
      select.appendChild(opt);
    });
    if (activeId && select.querySelector(`option[value="${activeId}"]`)) {
      select.value = activeId;
    }
  });
  syncCurrentUserInfo();
}

function syncCurrentUserInfo() {
  const user = getActiveUser();
  const settings = user ? user.settings || {} : {};
  safeText("current-user-name", settings.loginUser || "Unknown");
  safeText("current-user-ai", settings.aiName || defaults.aiName || "AI");
  safeText("current-user-id", user ? user.id : "-");
  const created = user && user.createdAt ? new Date(user.createdAt) : null;
  const createdText = created && !Number.isNaN(created.getTime()) ? created.toLocaleString() : "-";
  safeText("current-user-created", createdText);
}

function historyKey(userId) {
  const safeId = userId || "default";
  return `${HISTORY_KEY_PREFIX}${safeId}`;
}

function loadUserHistory(userId) {
  if (!userId) {
    return [];
  }
  try {
    const raw = localStorage.getItem(historyKey(userId));
    if (raw) {
      if (raw.length > MAX_HISTORY_BYTES) {
        reportIssue(
          "PHX-UI-701",
          "history_too_large",
          `bytes=${raw.length}`,
          { userId },
          "warn",
          false
        );
        return [];
      }
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.slice(-MAX_HISTORY);
      }
    }
  } catch (error) {
    // ignore
  }
  return [];
}

function saveUserHistory() {
  if (!state.activeUserId || state.historyDeferred) {
    return;
  }
  try {
    localStorage.setItem(
      historyKey(state.activeUserId),
      JSON.stringify(state.history.slice(-MAX_HISTORY))
    );
  } catch (error) {
    // ignore
  }
}

function pushHistory(role, content) {
  if (!content) {
    return;
  }
  state.history.push({ role, content });
  if (state.history.length > MAX_HISTORY) {
    state.history.splice(0, state.history.length - MAX_HISTORY);
  }
  saveUserHistory();
}

function renderChatHistory() {
  const log = $("chat-log");
  if (!log) {
    return;
  }
  log.innerHTML = "";
  const frag = document.createDocumentFragment();
  state.history.forEach((entry) => {
    if (!entry || !entry.role || !entry.content) {
      return;
    }
    if (entry.role === "user" || entry.role === "assistant") {
      if (entry.content === "[image]") {
        return;
      }
      const bubble = document.createElement("div");
      bubble.className = `chat-bubble ${entry.role}`;
      bubble.textContent = entry.content;
      frag.appendChild(bubble);
    }
  });
  log.appendChild(frag);
  log.scrollTop = log.scrollHeight;
  state.lastUserAt = 0;
  state.lastAssistantAt = 0;
}

function setActiveUser(userId, options = {}) {
  const {
    lockMode = "preserve",
    persist = true,
    renderHistory = true,
    loadHistory = true,
    deferHydration = false,
  } = options;
  if (!userId) {
    return;
  }
  if (state.activeUserId && state.activeUserId !== userId) {
    persistActiveUser();
  }
  const user = state.userStore.users.find((entry) => entry.id === userId);
  if (!user) {
    return;
  }
  state.activeUserId = user.id;
  state.settings = normalizeUserSettings(user.settings || {});
  state.history = loadHistory ? loadUserHistory(user.id) : [];
  state.historyDeferred = !loadHistory;
  state.userSessionHydrated = !deferHydration;
  state.audioProfilePrefs = loadAudioProfilePrefs(user.id);
  state.audioExamStatus = loadAudioExamStatus(user.id);
  state.audioHearingTest = {
    active: false,
    index: 0,
    target: "output",
    frequencies: [],
    results: [],
  };
  state.audioSpeechTest = {
    active: false,
    index: 0,
    phrases: [],
    expected: "",
    similarity: 0,
  };
  state.audioExam = {
    active: false,
    stage: "",
    startedAt: 0,
  };
    state.audioSuggestedEqBase = { input: [], output: [] };
    state.audioSuggestedEq = { input: [], output: [] };
    state.audioVoiceMetrics = { rms: null, peak: null };
    state.audioProfileStatus = "";
    state.emotionMap = loadOrbEmotionMap(user.id);
    state.emotionPrompt = {
      open: false,
      hz: null,
      bucket: null,
      palette: "gray",
      bandRange: "",
      state: "",
      reason: "",
      context: "",
    };
    state.emotionPromptSnooze = {};
    state.emotionPromptLastAt = 0;
    state.lastEmotionBucket = null;
    state.orbEmotion = "Unknown";
    state.orbFrequencyHz = null;
    state.lastUserAt = 0;
  state.lastAssistantAt = 0;
  state.lastProactiveAt = 0;
  state.pendingImage = null;
  state.pendingImageLoading = false;
  state.queuedMessage = null;
  clearPendingImage();
  if (renderHistory && loadHistory) {
    renderChatHistory();
  } else {
    const log = $("chat-log");
    if (log) {
      log.innerHTML = "";
    }
  }
  syncUserSelects();
  syncSettingsUI();
  if (!deferHydration) {
    syncAudioProfileLab();
  }
  applyBranding();
  updateOrbEmotionUI();
  if (lockMode === "lock") {
    state.locked = true;
  } else if (lockMode === "sync") {
    state.locked = Boolean(state.settings.loginEnabled);
  }
  applyLockState();
  applyPanelVisibility();
  document.querySelectorAll(".panel.floating").forEach((panel) => {
    restorePanelPosition(panel);
    clampPanel(panel);
  });
  if (!deferHydration) {
    renderAudioMedia();
  }
  if (persist) {
    saveUserStore();
  }
  saveUserHistory();
}

function hydrateUserSession() {
  if (state.userSessionHydrated || state.locked || !state.activeUserId) {
    return;
  }
  state.history = loadUserHistory(state.activeUserId);
  renderChatHistory();
  syncAudioProfileLab();
  renderAudioMedia();
  applyPanelVisibility();
  updateOrbEmotionUI();
  state.historyDeferred = false;
  state.userSessionHydrated = true;
}

function scheduleUserHydration() {
  if (state.userSessionHydrated || state.locked) {
    return;
  }
  const run = () => hydrateUserSession();
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(run, { timeout: 2000 });
  } else {
    setTimeout(run, 80);
  }
}

function setAdminStatus(message) {
  safeText("new-user-status", message || "Admin key required (DEV_ACCESS_KEY).");
}

async function ensureAdminUnlocked() {
  if (state.adminUnlocked) {
    return true;
  }
  const key = window.prompt("Enter DEV_ACCESS_KEY to create users:");
  if (!key) {
    setAdminStatus("Admin key required (DEV_ACCESS_KEY).");
    return false;
  }
  try {
    await api.devAccessCheck(key);
    state.adminUnlocked = true;
    setAdminStatus("Admin verified.");
    toast("Admin verified.", "info");
    return true;
  } catch (error) {
    setAdminStatus("Admin key rejected.");
    toast("Invalid admin key.", "warn");
    return false;
  }
}

const sounds = {};
const soundPaths = {
  system: "assets/sounds/system_thock.wav",
  alert: "assets/sounds/alert_system.wav",
  warn: "assets/sounds/alert_warning.wav",
  update: "assets/sounds/alert_update.wav",
  chime: "assets/sounds/reply_chime.wav",
};

function loadSounds() {
  Object.entries(soundPaths).forEach(([key, path]) => {
    const audio = new Audio(path);
    audio.preload = "auto";
    sounds[key] = audio;
  });
}

function playSound(key, volume = 1) {
  if (!state.audioSettings.systemSounds) {
    return;
  }
  if (state.audioSettings.hush && key !== "system") {
    return;
  }
  const audio = sounds[key];
  if (!audio) {
    return;
  }
  audio.volume = Math.max(0, Math.min(1, volume));
  audio.currentTime = 0;
  audio.play().catch(() => {});
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("read_failed"));
    reader.readAsDataURL(file);
  });
}

function setPendingImage(name, dataUrl) {
  state.pendingImage = { name, dataUrl };
  safeText("chat-attach-label", name || "Image ready");
}

function clearPendingImage() {
  state.pendingImage = null;
  safeText("chat-attach-label", "No image");
  const input = $("chat-image");
  if (input) {
    input.value = "";
  }
}

function toast(message, tone = "info") {
  if (state.audioSettings.hush && tone !== "info") {
    return;
  }
  if (tone === "alert" && !state.audioSettings.systemAlerts) {
    return;
  }
  if (tone === "warn" && !state.audioSettings.processWarnings) {
    return;
  }
  if (tone === "update" && !state.audioSettings.updateNotices) {
    return;
  }
  const stack = $("toast-stack");
  if (!stack) {
    return;
  }
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 4200);

  if (tone === "alert" && state.audioSettings.systemAlerts) {
    playSound("alert", state.audioSettings.volume / 100);
  }
  if (tone === "warn" && state.audioSettings.processWarnings) {
    playSound("warn", state.audioSettings.volume / 100);
  }
  if (tone === "update" && state.audioSettings.updateNotices) {
    playSound("update", state.audioSettings.volume / 100);
  }
}

function getWindowApi() {
  try {
    if (window.pywebview && window.pywebview.api) {
      return window.pywebview.api;
    }
  } catch {
    // ignore
  }
  try {
    if (window.parent && window.parent !== window && window.parent.pywebview?.api) {
      return window.parent.pywebview.api;
    }
  } catch {
    // ignore
  }
  return null;
}

async function callWindowApi(method) {
  const api = getWindowApi();
  if (!api || typeof api[method] !== "function") {
    return false;
  }
  try {
    await api[method]();
    return true;
  } catch {
    return false;
  }
}

function withTimeout(promise, ms, label) {
  if (!Number.isFinite(ms) || ms <= 0) {
    return promise;
  }
  return Promise.race([
    Promise.resolve(promise),
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(label || "timeout")), ms);
    }),
  ]);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function minimizeWindow() {
  const ok = (await callWindowApi("minimize")) || (await callWindowApi("hide"));
  if (!ok) {
    toast("Window minimize is only available in the desktop app.", "warn");
  }
}

async function ensureBackendOnline() {
  try {
    await api.ping();
    return true;
  } catch {
    // ignore
  }
  const started = await callWindowApi("start_backend");
  if (!started) {
    return false;
  }
  for (let i = 0; i < 12; i += 1) {
    try {
      await api.ping();
      return true;
    } catch {
      await delay(500);
    }
  }
  return false;
}

async function closeWindow() {
  const ok = (await callWindowApi("exit")) || (await callWindowApi("close"));
  if (ok) {
    return;
  }
  try {
    if (window.parent && window.parent !== window) {
      window.parent.close();
    } else {
      window.close();
    }
  } catch {
    // ignore
  }
}

function setOrbState(next, detail) {
  state.orbState = next;
  state.orbStateChangedAt = performance.now();
  state.orbEnergyTarget = getOrbEnergy(next);
  if (document.body) {
    document.body.dataset.orbState = next;
  }
  safeText("orb-label", next.toUpperCase());
  safeText("orb-state-line", `State: ${next}`);
  if (detail) {
    state.orbThought = detail;
  }
  safeText("orb-thoughts", `Thought stream: ${state.orbThought}`);
  const heart = $("orb-heart");
  if (heart) {
    if (state.awake) {
      heart.style.opacity = "1";
      safeText("orb-heartbeat-status", "Heartbeat: online");
    } else {
      heart.style.opacity = "0";
      safeText("orb-heartbeat-status", "Heartbeat: standby");
    }
  }
  applyHeartbeatSpeed();
}

function getOrbEnergy(stateName) {
  switch (stateName) {
    case "speaking":
      return 1;
    case "thinking":
      return 0.75;
    case "listening":
      return 0.5;
    case "dormant":
    default:
      return 0.25;
  }
}

function getHeartbeatBpm() {
  if (!state.awake || state.orbState === "dormant") {
    return 0;
  }
  let bpm = 66;
  switch (state.orbState) {
    case "thinking":
      bpm = 96;
      break;
    case "speaking":
      bpm = 82;
      break;
    case "listening":
      bpm = 64;
      break;
    default:
      bpm = 66;
  }
  const emotion = String(state.orbEmotion || "").toLowerCase();
  if (emotion.includes("relax") || emotion.includes("calm") || emotion.includes("ease")) {
    bpm = 58;
  } else if (
    emotion.includes("focused") ||
    emotion.includes("lock") ||
    emotion.includes("flow")
  ) {
    bpm = 92;
  } else if (
    emotion.includes("tense") ||
    emotion.includes("stress") ||
    emotion.includes("anxious") ||
    emotion.includes("fear")
  ) {
    bpm = 110;
  } else if (emotion.includes("excite") || emotion.includes("joy") || emotion.includes("happy")) {
    bpm = 98;
  }
  return bpm;
}

function getHeartbeatSeconds() {
  const bpm = getHeartbeatBpm();
  return bpm > 0 ? 60 / bpm : 0;
}

function getHeartbeatHz() {
  const bpm = getHeartbeatBpm();
  return bpm > 0 ? bpm / 60 : 0;
}

function applyHeartbeatSpeed() {
  const speed = getHeartbeatSeconds();
  const heart = $("orb-heart");
  if (!speed || !Number.isFinite(speed)) {
    document.documentElement.style.setProperty("--heartbeat-speed", "0s");
    state.orbHeartbeatHz = 0;
    if (heart) {
      heart.style.animation = "none";
    }
    stopOrbHeartbeatLoop();
    return;
  }
  document.documentElement.style.setProperty("--heartbeat-speed", `${speed.toFixed(2)}s`);
  state.orbHeartbeatHz = Number(getHeartbeatHz().toFixed(3));
  if (heart) {
    heart.style.animation = "";
  }
  if (state.awake) {
    startOrbHeartbeatLoop();
  }
}

function getOrbImageCooldownMs() {
  if (!state.awake || state.orbState === "dormant") {
    return Infinity;
  }
  if (state.settings.performanceFocusEnabled || state.autoPerfActive) {
    return Infinity;
  }
  if (state.orbState === "thinking") {
    return 5200;
  }
  if (state.orbState === "speaking") {
    return 6800;
  }
  if (state.orbState === "listening") {
    return 9800;
  }
  return 9000;
}

async function maybeRequestOrbImage() {
  if (!state.orbImageEnabled || !state.awake) {
    return;
  }
  if (state.settings.performanceFocusEnabled || state.autoPerfActive) {
    return;
  }
  if (!state.settings.animations) {
    return;
  }
  if (state.chatBusy || state.pendingImageLoading) {
    return;
  }
  if (state.orbImageInFlight) {
    return;
  }
  const thought = String(state.orbThought || "").trim();
  if (!thought || thought === "idle" || thought === "processing") {
    return;
  }
  const now = Date.now();
  const cooldown = getOrbImageCooldownMs();
  if (Number.isFinite(cooldown) && now - state.orbImageLastAt < cooldown) {
    return;
  }
  state.orbImageInFlight = true;
  state.orbImageLastAt = now;
  try {
    const response = await api.orbImage({
      thought,
      emotion: state.orbEmotion || "Unknown",
      state: state.orbState || "listening",
      heartbeatHz: state.orbHeartbeatHz || getHeartbeatHz(),
    });
    if (response && response.dataUrl) {
      state.orbImageDataUrl = response.dataUrl;
      state.orbImageKey = response.key || `${thought}:${Date.now()}`;
    }
  } catch (error) {
    logUiError("orb_image_failed", error?.message || String(error));
  } finally {
    state.orbImageInFlight = false;
  }
}

function addChat(role, text) {
  const log = $("chat-log");
  if (!log) {
    return;
  }
  const now = Date.now();
  if (role === "user") state.lastUserAt = now;
  if (role === "assistant") state.lastAssistantAt = now;
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = text;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

function addChatImage(role, dataUrl) {
  const log = $("chat-log");
  if (!log || !dataUrl) {
    return;
  }
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role} image`;
  const img = document.createElement("img");
  img.className = "chat-image-preview";
  img.alt = "image";
  img.src = dataUrl;
  bubble.appendChild(img);
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

function parseOrbDirectives(text) {
  const result = { cleaned: text, action: "", override: null };
  if (!text) {
    return result;
  }

  result.cleaned = result.cleaned.replace(/\[orb:([^\]]+)\]/gi, (match, content) => {
    const raw = String(content || "").trim();
    if (!raw) {
      return "";
    }
    const lower = raw.toLowerCase();
    if (lower.startsWith("clear") || lower.startsWith("reset")) {
      result.override = { mode: "clear" };
      result.action = "";
      return "";
    }
    if (lower.startsWith("pattern")) {
      const override = { mode: "pattern" };
      const nums = raw.split(":")[1];
      if (nums) {
        const parts = nums.split(",").map((p) => parseFloat(p.trim())).filter((n) => Number.isFinite(n));
        if (parts[0]) override.a = Math.max(2, Math.min(9, Math.round(parts[0])));
        if (parts[1]) override.b = Math.max(2, Math.min(9, Math.round(parts[1])));
        if (parts[2]) override.amp = Math.max(60, Math.min(180, parts[2]));
      }
      const match = raw.match(/a\s*=\s*([0-9.]+)/i);
      if (match) override.a = Math.max(2, Math.min(9, parseFloat(match[1])));
      const matchB = raw.match(/b\s*=\s*([0-9.]+)/i);
      if (matchB) override.b = Math.max(2, Math.min(9, parseFloat(matchB[1])));
      const matchAmp = raw.match(/amp\s*=\s*([0-9.]+)/i);
      if (matchAmp) override.amp = Math.max(60, Math.min(180, parseFloat(matchAmp[1])));
      const matchRot = raw.match(/rot\s*=\s*([0-9.]+)/i);
      if (matchRot) override.rot = parseFloat(matchRot[1]);
      result.override = override;
      return "";
    }
    if (lower.includes("wave")) {
      result.override = { mode: "waveform" };
      return "";
    }
    if (lower.includes("glyph") || lower.includes("swarm")) {
      result.override = { mode: "glyphs" };
      return "";
    }
    if (lower.startsWith("text:")) {
      result.action = raw.split(":").slice(1).join(":").trim();
      return "";
    }
    if (lower.startsWith("action")) {
      result.action = raw.replace(/action\s*:/i, "").trim();
      return "";
    }
    result.action = raw;
    return "";
  });

  const actionMatches = [...result.cleaned.matchAll(/\*{1,2}([^*]{2,40})\*{1,2}/g)];
  if (actionMatches.length) {
    const action = actionMatches[actionMatches.length - 1][1].trim();
    if (action) {
      result.action = action;
    }
  }
  result.cleaned = result.cleaned.replace(/\*{1,2}[^*]{2,40}\*{1,2}/g, " ").replace(/\s{2,}/g, " ").trim();
  return result;
}

function showPrompt({ id, title, body, actions = [] }) {
  if (prompts.has(id)) {
    return;
  }
  const stack = $("prompt-stack");
  if (!stack) {
    return;
  }
  const card = document.createElement("div");
  card.className = "prompt-card";
  card.dataset.promptId = id;

  const titleEl = document.createElement("div");
  titleEl.className = "prompt-title";
  titleEl.textContent = title;
  card.appendChild(titleEl);

  const bodyEl = document.createElement("div");
  bodyEl.className = "prompt-body";
  bodyEl.textContent = body;
  card.appendChild(bodyEl);

  const actionRow = document.createElement("div");
  actionRow.className = "prompt-actions";
  actions.forEach((action) => {
    const btn = document.createElement("button");
    btn.className = `btn ${action.tone === "primary" ? "primary" : "ghost"}`;
    btn.textContent = action.label;
    btn.addEventListener("click", () => {
      if (action.onClick) {
        action.onClick();
      }
      removePrompt(id);
    });
    actionRow.appendChild(btn);
  });
  const dismiss = document.createElement("button");
  dismiss.className = "btn ghost";
  dismiss.textContent = "Dismiss";
  dismiss.addEventListener("click", () => removePrompt(id));
  actionRow.appendChild(dismiss);
  card.appendChild(actionRow);

  stack.appendChild(card);
  prompts.set(id, card);
  placePrompt(card);
  registerPromptDrag(card);
  reflowPrompts();
}

function removePrompt(id) {
  const card = prompts.get(id);
  if (!card) {
    return;
  }
  card.remove();
  prompts.delete(id);
  reflowPrompts();
}

function placePrompt(card) {
  const index = Math.max(0, prompts.size - 1);
  card.style.right = "4vw";
  card.style.bottom = `${6 + index * 110}px`;
}

function reflowPrompts() {
  let offset = 0;
  prompts.forEach((card) => {
    if (card.dataset.pinned === "true") {
      return;
    }
    card.style.right = "4vw";
    card.style.bottom = `${6 + offset * 110}px`;
    offset += 1;
  });
}

function registerPromptDrag(card) {
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;
  let dragging = false;

  function onMouseDown(event) {
    if (!(event.button === 1 || (event.button === 0 && event.ctrlKey))) {
      return;
    }
    event.preventDefault();
    dragging = true;
    startX = event.clientX;
    startY = event.clientY;
    startLeft = card.offsetLeft;
    startTop = card.offsetTop;
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp, { once: true });
  }

  function onMouseMove(event) {
    if (!dragging) {
      return;
    }
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    card.style.left = `${startLeft + dx}px`;
    card.style.top = `${startTop + dy}px`;
    card.style.right = "auto";
    card.style.bottom = "auto";
  }

  function onMouseUp() {
    dragging = false;
    document.removeEventListener("mousemove", onMouseMove);
    card.dataset.pinned = "true";
    const offRight = card.offsetLeft > window.innerWidth - 80;
    const offLeft = card.offsetLeft < -120;
    if (offRight || offLeft) {
      removePrompt(card.dataset.promptId);
    }
  }

  card.addEventListener("mousedown", onMouseDown);
}

function loadSettings() {
  const { store, loaded } = loadUserStore();
  state.userStore = store;
  setActiveUser(store.activeId, {
    lockMode: "preserve",
    persist: true,
    renderHistory: false,
    loadHistory: false,
    deferHydration: true,
  });
  setAdminStatus();
  return loaded;
}

function saveSettings() {
  state.settings.theme = normalizeTheme(state.settings.theme);
  persistActiveUser();
  saveUserHistory();
  syncUserSelects();
  applyBranding();
  api
    .settingsSet(state.settings)
    .catch(() => {});
}

function normalizeTheme(theme) {
  return { ...defaults.theme, ...(theme || {}) };
}

function applyTheme() {
  const theme = normalizeTheme(state.settings.theme);
  const root = document.documentElement.style;
  root.setProperty("--bg", theme.bg);
  root.setProperty("--panel", theme.panel);
  root.setProperty("--panel-border", theme.panelBorder);
  root.setProperty("--accent", theme.accent);
  root.setProperty("--accent-strong", theme.accentStrong);
  root.setProperty("--accent-soft", theme.accentSoft);
  root.setProperty("--text", theme.text);
  root.setProperty("--muted", theme.muted);
  state.settings.theme = theme;
}

function normalizeHexColor(value) {
  if (!value) {
    return "";
  }
  const trimmed = String(value).trim();
  if (/^#[0-9a-f]{6}$/i.test(trimmed)) {
    return trimmed.toLowerCase();
  }
  const shortMatch = trimmed.match(/^#([0-9a-f]{3})$/i);
  if (shortMatch) {
    return `#${shortMatch[1]
      .split("")
      .map((char) => char + char)
      .join("")}`.toLowerCase();
  }
  return "";
}

function parseRgbColor(value) {
  if (!value) {
    return "";
  }
  const match = String(value).trim().match(/^rgba?\(([^)]+)\)$/i);
  if (!match) {
    return "";
  }
  const parts = match[1]
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length < 3) {
    return "";
  }
  const numbers = parts.slice(0, 3).map((part) => Number.parseFloat(part));
  if (numbers.some((num) => Number.isNaN(num))) {
    return "";
  }
  const clamp = (num) => Math.max(0, Math.min(255, Math.round(num)));
  return `#${numbers
    .map((num) => clamp(num).toString(16).padStart(2, "0"))
    .join("")}`;
}

function colorToHex(value, fallback) {
  const direct = normalizeHexColor(value);
  if (direct) {
    return direct;
  }
  const rgb = parseRgbColor(value);
  if (rgb) {
    return rgb;
  }
  return normalizeHexColor(fallback) || "#000000";
}

function applyLockState() {
  const overlay = $("login-overlay");
  const secondaryOverlay = $("secondary-overlay");
  if (!overlay) {
    return;
  }
  const locked = state.locked && !state.loading;
  if (state.secondaryDisplay) {
    overlay.classList.add("hidden");
    if (secondaryOverlay) {
      secondaryOverlay.classList.toggle("hidden", !locked);
    }
  } else {
    overlay.classList.toggle("hidden", !locked);
    if (secondaryOverlay) {
      secondaryOverlay.classList.add("hidden");
    }
  }
  document.body.classList.toggle("locked", locked);
  const userLabel = $("login-user-label");
  if (userLabel) {
    userLabel.textContent = state.settings.loginUser || "Phoenix";
  }
  const aiLabel = $("login-ai-label");
  if (aiLabel) {
    const aiName = state.settings.aiName || defaults.aiName || "";
    aiLabel.textContent = aiName ? `AI: ${aiName}` : "";
  }
  const input = $("login-password");
  if (state.locked && input && !state.secondaryDisplay) {
    input.value = "";
    input.focus();
  }
  applyPanelVisibility();
}

function applyLoadingState() {
  const overlay = $("loading-overlay");
  const isLoading = state.loading || Boolean(state.bootError);
  if (overlay) {
    overlay.classList.toggle("hidden", !isLoading);
  }
  document.body.classList.toggle("booting", isLoading);
}

function attemptUnlock() {
  try {
    if (!state.settings.loginEnabled) {
      state.locked = false;
      applyLockState();
      return;
    }
    const input = $("login-password");
    const typed = input ? input.value : "";
    if (String(typed || "") === String(state.settings.loginPass || "")) {
      state.locked = false;
      applyLockState();
      initPostLogin();
      scheduleUserHydration();
      startLoops();
      toast("Access granted.", "info");
      return;
    }
    if (input) {
      input.value = "";
      input.focus();
    }
    toast("Invalid password.", "warn");
  } catch (error) {
    logUiError("login_unlock_failed", error?.message || String(error));
    toast("Login error. Check logs.", "warn");
  }
}

function initLogin() {
  state.locked = Boolean(state.settings.loginEnabled);
  applyLockState();
  syncUserSelects();
  on("login-user-select", "change", (event) => {
    const selected = event.target.value;
    if (selected && selected !== state.activeUserId) {
      setActiveUser(selected, {
        lockMode: "preserve",
        persist: true,
        renderHistory: false,
        loadHistory: false,
        deferHydration: true,
      });
    }
  });
  on("login-unlock", "click", attemptUnlock);
  on("login-password", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      attemptUnlock();
    }
  });
  on("login-toggle", "click", () => {
    const input = $("login-password");
    const btn = $("login-toggle");
    if (!input || !btn) {
      return;
    }
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Hide" : "Show";
  });
}

function requireUnlocked() {
  if (state.loading) {
    toast("Systems are still loading.", "info");
    return false;
  }
  if (!state.locked) {
    return true;
  }
  toast("Unlock to proceed.", "warn");
  return false;
}

function syncSettingsUI() {
  const audioChecked = [
    ["setting-system-sounds", "systemSounds"],
    ["setting-voice-feedback", "voiceFeedback"],
    ["setting-reply-chime", "replyChime"],
    ["setting-hush", "hush"],
    ["setting-system-alerts", "systemAlerts"],
    ["setting-process-warnings", "processWarnings"],
    ["setting-update-notices", "updateNotices"],
  ];
  audioChecked.forEach(([id, key]) => {
    const el = $(id);
    if (el) {
      el.checked = Boolean(state.audioSettings[key]);
    }
  });
    const uiChecked = [
      ["setting-login-enabled", "loginEnabled"],
      ["setting-show-chat", "showChat"],
      ["setting-show-system", "showSystem"],
      ["setting-show-frequency", "showFrequency"],
      ["setting-show-orbtools", "showOrbTools"],
      ["setting-show-audio", "showAudio"],
      ["setting-show-perf", "showPerf"],
      ["setting-emotion-prompts", "emotionPromptEnabled"],
      ["setting-performance-focus", "performanceFocusEnabled"],
      ["setting-desktop-view", "desktopViewEnabled"],
      ["usb-include-os", "usbIncludeOs"],
      ["usb-include-app", "usbIncludeApp"],
      ["usb-include-memory", "usbIncludeMemory"],
      ["usb-include-user", "usbIncludeUserData"],
    ];
  uiChecked.forEach(([id, key]) => {
    const el = $(id);
    if (el) {
      el.checked = Boolean(state.settings[key]);
    }
  });
  const volume = $("setting-volume");
  if (volume) {
    volume.value = state.audioSettings.volume;
  }
  const chime = $("setting-chime");
  if (chime) {
    chime.value = state.audioSettings.chimeVolume;
  }
  const voice = $("setting-voice");
  if (voice) {
    voice.value = state.audioSettings.voice;
  }
  const rate = $("setting-rate");
  if (rate) {
    rate.value = state.audioSettings.rate;
  }
  const pitch = $("setting-pitch");
  if (pitch) {
    pitch.value = state.audioSettings.pitch;
  }
  const eqConfig = $("audio-eq-config-path");
  if (eqConfig) {
    eqConfig.value = state.audioSettings.eqApoConfigPath || "";
  }
  const mediaSource = $("audio-media-source");
  if (mediaSource) {
    mediaSource.value = state.audioSettings.mediaSource || audioDefaults.mediaSource;
  }
  const spotifyUrl = $("audio-spotify-url");
  if (spotifyUrl) {
    spotifyUrl.value = state.audioSettings.spotifyUrl || "";
  }
  const loginUser = $("setting-login-user");
  if (loginUser) {
    loginUser.value = state.settings.loginUser || "";
  }
  const loginPass = $("setting-login-pass");
  if (loginPass) {
    loginPass.value = state.settings.loginPass || "";
  }
  const aiName = $("setting-ai-name");
  if (aiName) {
    aiName.value = state.settings.aiName || "";
  }
  const usbLocalBoot = $("setting-usb-local-boot");
  if (usbLocalBoot) {
    usbLocalBoot.checked = Boolean(state.settings.usbLocalBootEnabled);
  }
  const usbLocalPath = $("setting-usb-local-path");
  if (usbLocalPath) {
    usbLocalPath.value = state.settings.usbLocalBootPath || "";
  }
  const remoteEnabled = $("setting-remote-enabled");
  if (remoteEnabled) {
    remoteEnabled.checked = Boolean(state.settings.remoteUiEnabled);
  }
  const remoteHost = $("setting-remote-host");
  if (remoteHost) {
    remoteHost.value = state.settings.remoteUiHost || "";
  }
  const remoteTunnel = $("setting-remote-tunnel");
  if (remoteTunnel) {
    remoteTunnel.checked = Boolean(state.settings.remoteTunnelEnabled);
  }
  syncUsbPresetUI();

  const theme = normalizeTheme(state.settings.theme);
  const themeFields = [
    ["setting-theme-bg", "setting-theme-bg-color", "bg", defaults.theme.bg],
    ["setting-theme-panel", "setting-theme-panel-color", "panel", defaults.theme.panel],
    [
      "setting-theme-panel-border",
      "setting-theme-panel-border-color",
      "panelBorder",
      defaults.theme.panelBorder,
    ],
    ["setting-theme-accent", "setting-theme-accent-color", "accent", defaults.theme.accent],
    [
      "setting-theme-accent-strong",
      "setting-theme-accent-strong-color",
      "accentStrong",
      defaults.theme.accentStrong,
    ],
    [
      "setting-theme-accent-soft",
      "setting-theme-accent-soft-color",
      "accentSoft",
      defaults.theme.accentSoft,
    ],
    ["setting-theme-text", "setting-theme-text-color", "text", defaults.theme.text],
    ["setting-theme-muted", "setting-theme-muted-color", "muted", defaults.theme.muted],
  ];
  const themeFieldMap = {
    bg: { textId: "setting-theme-bg", colorId: "setting-theme-bg-color" },
    panel: { textId: "setting-theme-panel", colorId: "setting-theme-panel-color" },
    panelBorder: {
      textId: "setting-theme-panel-border",
      colorId: "setting-theme-panel-border-color",
    },
    accent: { textId: "setting-theme-accent", colorId: "setting-theme-accent-color" },
    accentStrong: {
      textId: "setting-theme-accent-strong",
      colorId: "setting-theme-accent-strong-color",
    },
    accentSoft: {
      textId: "setting-theme-accent-soft",
      colorId: "setting-theme-accent-soft-color",
    },
    text: { textId: "setting-theme-text", colorId: "setting-theme-text-color" },
    muted: { textId: "setting-theme-muted", colorId: "setting-theme-muted-color" },
  };

  const hexToRgb = (hex) => {
    const normalized = normalizeHexColor(hex);
    if (!normalized) return null;
    const value = normalized.slice(1);
    return {
      r: parseInt(value.slice(0, 2), 16),
      g: parseInt(value.slice(2, 4), 16),
      b: parseInt(value.slice(4, 6), 16),
    };
  };

  const applyWheelColor = (key, hex) => {
    const entry = themeFieldMap[key];
    if (!entry) return;
    const textEl = $(entry.textId);
    const colorEl = $(entry.colorId);
    let nextValue = hex;
    const existing = textEl ? textEl.value.trim() : "";
    if (/^rgba\(/i.test(existing)) {
      const match = existing.match(/rgba\([^,]+,[^,]+,[^,]+,([^)]+)\)/i);
      const alpha = match ? Number.parseFloat(match[1]) : Number.NaN;
      const rgb = hexToRgb(hex);
      if (rgb && Number.isFinite(alpha)) {
        nextValue = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
      }
    }
    if (textEl) {
      textEl.value = nextValue;
    }
    if (colorEl) {
      colorEl.value = normalizeHexColor(hex) || colorEl.value;
    }
    state.settings.theme = { ...state.settings.theme, [key]: nextValue };
    applyTheme();
    saveSettings();
  };

  const syncThemeWheel = () => {
    const target = $("theme-wheel-target");
    const picker = $("theme-wheel-picker");
    const hexOut = $("theme-wheel-hex");
    if (!target || !picker || !hexOut) return;
    const key = target.value || "accent";
    const entry = themeFieldMap[key];
    if (!entry) return;
    const textEl = $(entry.textId);
    const color = colorToHex(textEl ? textEl.value : "", defaults.theme[key] || "#3ef2e0");
    picker.value = color;
    hexOut.value = color;
  };
  themeFields.forEach(([textId, colorId, key, fallback]) => {
    const textEl = $(textId);
    if (textEl) {
      textEl.value = theme[key] || "";
    }
    const colorEl = $(colorId);
    if (colorEl) {
      colorEl.value = colorToHex(theme[key], fallback);
    }
  });
  syncThemeWheel();
  applyTheme();
  applyBranding();
  syncUserSelects();
  safeText(
    "orb-audio",
    state.audioSettings.voiceFeedback ? "Voice: enabled" : "Voice: muted"
  );

  if (state.userSessionHydrated) {
    syncAudioProfileLab();
    renderAudioMedia();
  }
  applyPanelVisibility();
}

function updateAudioProfileStatus(message) {
  if (message) {
    state.audioProfileStatus = message;
  }
  const status = state.audioProfileStatus || "Audio profile ready.";
  safeText("audio-profile-status", status);
}

function syncAudioProfileLab() {
  state.audioProfilePrefs = normalizeAudioProfilePrefs(state.audioProfilePrefs);
  const prefBindings = [
    ["audio-pref-warmth", "audio-pref-warmth-value", "warmth"],
    ["audio-pref-clarity", "audio-pref-clarity-value", "clarity"],
    ["audio-pref-air", "audio-pref-air-value", "air"],
    ["audio-pref-bass", "audio-pref-bass-value", "bass"],
  ];
  prefBindings.forEach(([inputId, valueId, key]) => {
    const input = $(inputId);
    const valueEl = $(valueId);
    if (input) {
      input.value = String(state.audioProfilePrefs[key]);
    }
    if (valueEl) {
      valueEl.textContent = String(state.audioProfilePrefs[key]);
    }
  });
  const hearingTarget = $("audio-hearing-target");
  if (hearingTarget) {
    hearingTarget.value = state.audioHearingTest.target || "output";
  }
  const examSteps = $("audio-exam-steps");
  if (examSteps) {
    examSteps.classList.toggle("hidden", !state.audioExam.active);
  }
  const examStart = $("audio-exam-start");
  const examStop = $("audio-exam-stop");
  const completedAt = state.audioExamStatus.completedAt;
  const examCompleted = Boolean(completedAt);
  if (examStart) {
    examStart.textContent = examCompleted ? "Run exam again" : "Start full exam";
    examStart.disabled = state.audioExam.active;
  }
  if (examStop) {
    examStop.disabled = !state.audioExam.active;
  }
  const examStatus = $("audio-exam-status");
  if (examStatus) {
    if (examCompleted) {
      const stamp = formatExamTimestamp(completedAt);
      const runs = state.audioExamStatus.runCount || 0;
      examStatus.textContent = stamp ? `Completed ${stamp} (runs: ${runs})` : `Completed (runs: ${runs})`;
    } else {
      examStatus.textContent = "Not run yet.";
    }
  }
  const voiceRms = $("audio-voice-rms");
  const voicePeak = $("audio-voice-peak");
  if (voiceRms) {
    voiceRms.textContent =
      state.audioVoiceMetrics.rms !== null ? state.audioVoiceMetrics.rms.toFixed(3) : "--";
  }
  if (voicePeak) {
    voicePeak.textContent =
      state.audioVoiceMetrics.peak !== null ? state.audioVoiceMetrics.peak.toFixed(3) : "--";
  }
  updateHearingStatus();
  updateSpeechStatus();
  if (!state.audioExam.active) {
    if (state.audioExamStatus.completedAt) {
      setExamPrompt("Exam completed. Run again if you want to recalibrate.");
    } else {
      setExamPrompt("Ready for exam.");
    }
  }
  refreshSuggestedEqFromPrefs();
  updateAudioProfileStatus(state.audioProfileStatus);
}

function applyPerfFocusClass() {
  const enabled = Boolean(
    state.settings.performanceFocusEnabled ||
      state.autoPerfActive ||
      state.uiHidden ||
      state.locked ||
      state.loading ||
      !state.awake
  );
  if (document.body) {
    document.body.classList.toggle("perf-focus", enabled);
  }
}

function applyPanelVisibility() {
  applyPerfFocusClass();
  if (state.minimal) {
    togglePanel("panel-controls", false);
    togglePanel("panel-chat", false);
    togglePanel("panel-system", false);
    togglePanel("panel-frequency", false);
    togglePanel("panel-orb-tools", false);
    togglePanel("panel-audio", false);
    togglePanel("panel-emotion", false);
    togglePanel("panel-artificer", false);
    togglePanel("panel-perf", false);
    return;
  }
  const focus = Boolean(state.settings.performanceFocusEnabled);
  const showCore = state.activeModule === "core" || state.activeModule === "all";
  const showFrequency = state.activeModule === "frequency" || state.activeModule === "all";
  const showAudio = state.activeModule === "audio" || state.activeModule === "all";
  const showArtificer = state.activeModule === "artificer" || state.activeModule === "all";
  togglePanel("panel-controls", !focus);
  togglePanel("panel-chat", showCore && state.settings.showChat && state.awake);
  togglePanel("panel-system", showCore && state.settings.showSystem && !focus);
  togglePanel("panel-perf", showCore && state.settings.showPerf && !focus);
  togglePanel("panel-frequency", showFrequency && state.settings.showFrequency);
  togglePanel("panel-orb-tools", showCore && state.settings.showOrbTools && !focus);
  togglePanel("panel-audio", showAudio && state.settings.showAudio);
  togglePanel("panel-artificer", showArtificer);
  togglePanel(
    "panel-emotion",
    state.emotionPrompt.open &&
      state.settings.emotionPromptEnabled &&
      state.awake &&
      !state.locked &&
      !focus
  );
}

function syncWakeButtons() {
  const wake = $("btn-wake");
  const sleep = $("btn-sleep");
  if (wake) {
    wake.style.display = state.awake ? "none" : "inline-flex";
  }
  if (sleep) {
    sleep.style.display = state.awake ? "inline-flex" : "none";
  }
}

function togglePanel(id, show) {
  const el = $(id);
  if (!el) {
    return;
  }
  el.style.display = show ? "flex" : "none";
  if (show) {
    if (state.layoutReady && !hasStoredPosition(el)) {
      const offset = cascadeOffset(el);
      centerPanel(el, offset.x, offset.y);
      savePanelPosition(el);
    } else {
      clampPanel(el);
    }
  }
}

function setActiveModule(moduleName) {
  state.activeModule = moduleName;
  const select = $("module-select");
  if (select && moduleName !== "frequency") {
    select.value = moduleName;
  }
  if (moduleName === "frequency" && !state.settings.showFrequency) {
    state.settings.showFrequency = true;
    saveSettings();
  }
  const freqBtn = $("btn-frequency");
  if (freqBtn) {
    freqBtn.classList.toggle("active", moduleName === "frequency");
  }
  if (moduleName === "audio" || moduleName === "all") {
    if (!state.audioDevicesLoaded) {
      refreshAudioDevices();
    }
    refreshAudioEq();
    refreshAudioProfiles();
    refreshAudioSystemMix();
    refreshAudioEqEngine();
    refreshSpotifyStatus();
  }
  applyPanelVisibility();
}

// Queue a visualization request so the orb "thinks" with the swarm for N seconds.
function queueVisualization(thought, seconds = 5) {
  const now = performance.now();
  state.visualization = {
    thought: thought || "an idea",
    until: now + Math.max(1, seconds) * 1000,
    started: now,
    done: false,
  };
  state.orbOverride = { mode: "glyphs", text: thought };
  state.orbOverrideUntil = state.visualization.until;
  state.orbThought = thought.slice(0, 80);
  safeText("orb-thoughts", `Thought stream: ${state.orbThought}`);
  setOrbState("thinking", "processing");
}

async function updateStatus() {
  try {
    const ping = await api.ping();
    safeText("backend-pill", "Backend: online");
    removePrompt("backend-offline");
    try {
      const mem = await api.memoryInfo();
      safeText("memory-pill", `Memory: ${mem.count ?? "?"}`);
      if (!mem.count || mem.count < 1) {
        showPrompt({
          id: "memory-empty",
          title: "Memory missing",
          body: "Memory store looks empty. Inject now?",
          actions: [
            {
              label: "Inject",
              tone: "primary",
              onClick: () => api.memoryReload().catch(() => {}),
            },
          ],
        });
      } else {
        removePrompt("memory-empty");
      }
    } catch (error) {
      safeText("memory-pill", "Memory: ?");
    }
    safeText("diag-cpu", `${Math.round(ping.cpu_percent || 0)}%`);
    safeText("diag-mem", `${Math.round(ping.memory_percent || 0)}%`);
    safeText("diag-gpu", `${Math.round(ping.gpu_percent || 0)}%`);
    safeText("diag-temp", "--");
    const uptime = Number(ping.uptime || 0);
    const hours = String(Math.floor(uptime / 3600)).padStart(2, "0");
    const minutes = String(Math.floor((uptime % 3600) / 60)).padStart(2, "0");
    const seconds = String(uptime % 60).padStart(2, "0");
    safeText("diag-uptime", `${hours}:${minutes}:${seconds}`);
    safeText("diag-proc", `${ping.processes || "--"}`);
    safeText("diag-net", "online");
  } catch (error) {
    safeText("backend-pill", "Backend: offline");
    reportIssue(
      "PHX-NET-101",
      "backend_offline",
      error?.message || String(error),
      { apiBase: api.baseUrl || "" },
      "warn",
      true
    );
    showPrompt({
      id: "backend-offline",
      title: "Backend offline",
      body: "Wake systems to reconnect.",
      actions: [
        { label: "Wake", tone: "primary", onClick: wakeSystems },
        { label: "Retry", tone: "ghost", onClick: updateStatus },
      ],
    });
  }
}

function maybeProactive() {
  if (!state.awake || state.chatBusy || state.visualization) {
    return;
  }
  const now = Date.now();
  const idleSinceUser = state.lastUserAt ? now - state.lastUserAt : Infinity;
  const idleSinceAssistant = state.lastAssistantAt ? now - state.lastAssistantAt : Infinity;
  if (now - state.lastProactiveAt < 180000) {
    return;
  }
  if (idleSinceUser > 120000 && idleSinceAssistant > 90000) {
    state.lastProactiveAt = now;
    const prompt = "Status check: anything you'd like me to focus on?";
    addChat("assistant", prompt);
    pushHistory("assistant", "[proactive] " + prompt);
    setOrbState("listening", "idle");
  }
}

async function checkOllama() {
  if (!state.awake) {
    safeText("ollama-pill", "Ollama: standby");
    removePrompt("ollama-offline");
    return;
  }
  try {
    const status = await api.ollamaStatus();
    safeText("ollama-pill", status.ok ? "Ollama: ready" : "Ollama: offline");
    if (!status.ok) {
      showPrompt({
        id: "ollama-offline",
        title: "Ollama offline",
        body: "Start local model service?",
        actions: [
          { label: "Start", tone: "primary", onClick: () => api.ollamaStart().catch(() => {}) },
        ],
      });
    } else {
      removePrompt("ollama-offline");
    }
  } catch (error) {
    safeText("ollama-pill", "Ollama: offline");
    showPrompt({
      id: "ollama-offline",
      title: "Ollama offline",
      body: "Start local model service?",
      actions: [
        { label: "Start", tone: "primary", onClick: () => api.ollamaStart().catch(() => {}) },
      ],
    });
  }
}

async function wakeSystems() {
  setOrbState("listening", "booting");
  try {
    const ready = await ensureBackendOnline();
    if (!ready) {
      throw new Error("Backend offline");
    }
    await api.memoryReload();
    await api.ollamaStart();
    await api.wake();
    state.awake = true;
    startUiHeartbeat();
    startOrbHeartbeatLoop();
    setOrbState("listening", "online");
    safeText(
      "orb-audio",
      state.audioSettings.voiceFeedback ? "Voice: enabled" : "Voice: muted"
    );
    applyPanelVisibility();
    syncWakeButtons();
    toast("Systems awake.");
    playSound("system", state.audioSettings.volume / 100);
  } catch (error) {
    reportIssue(
      "PHX-UI-101",
      "wake_failed",
      error?.message || String(error),
      { apiBase: api.baseUrl || "" },
      "error",
      true
    );
    fireAndForget(api.logClient?.("wake_failed", error?.message || String(error)));
    toast("Wake failed.", "alert");
    setOrbState("dormant");
  }
}

async function sleepSystems() {
  try {
    await withTimeout(api.sleep(), 2000, "sleep timeout");
  } catch (error) {
    reportIssue("PHX-UI-102", "sleep_failed", error?.message || String(error), {}, "warn", true);
    toast("Sleep request failed.", "warn");
  }
  stopUiHeartbeat();
  stopOrbHeartbeatLoop();
  state.awake = false;
  setOrbState("dormant");
  applyPanelVisibility();
  syncWakeButtons();
  safeText("orb-audio", "Voice: muted");
}

async function shutdownApp() {
  await flushStateOnExit();
  sleepSystems().catch(() => {});
  await closeWindow();
}

function rebootProject() {
  if (!requireUnlocked()) {
    return;
  }
  showPrompt({
    id: "reboot-project",
    title: "Reboot Phoenix-15?",
    body: "This will close and relaunch the full project.",
    actions: [
      {
        label: "Reboot",
        tone: "primary",
        onClick: async () => {
          toast("Rebooting project...", "info");
          await flushStateOnExit();
          try {
            const ready = await ensureBackendOnline();
            if (ready) {
              await api.reboot();
              await delay(300);
              await closeWindow();
              return;
            }
            throw new Error("Backend offline");
          } catch (error) {
            const fallback = await callWindowApi("reboot");
            if (fallback) {
              toast("Rebooting via launcher...", "info");
              await closeWindow();
              return;
            }
            logUiError("reboot_failed", error?.message || String(error));
            toast("Reboot failed. Check logs.", "warn");
          }
        },
      },
    ],
  });
}

async function selfCheck() {
  try {
    const data = await api.selfcheck();
    const checks = Array.isArray(data.checks) ? data.checks : [];
    const failed = checks.filter((item) => item && item.ok === false);
    if (failed.length) {
      const codes = failed.map((item) => item.code).filter(Boolean).join(", ");
      toast(
        `Self-check issues (${failed.length}): ${codes || "see Phoenix-15_FIXME_log"}`,
        "alert"
      );
      fireAndForget(api.logIssue?.({
        code: "PHX-SYS-900",
        message: "selfcheck_failures",
        detail: codes,
        severity: "error",
        source: "ui",
        context: { count: failed.length },
      }));
    } else {
      toast(
        `Self-check OK. CPU ${Math.round(data.cpu || 0)}% / MEM ${Math.round(data.memory || 0)}%`
      );
    }
  } catch (error) {
    toast("Self-check failed (PHX-SYS-999).", "warn");
    fireAndForget(api.logIssue?.({
      code: "PHX-SYS-999",
      message: "selfcheck_failed",
      detail: error?.message || String(error),
      severity: "error",
      source: "ui",
    }));
  }
}

async function memoryCheck() {
  try {
    const info = await api.memoryCheck();
    const count = info.count ?? 0;
    const hint = info.hint || "";
    if (!count || count < 1) {
      await api.memoryReload();
      toast("Memory reinjected.");
    } else {
      toast(`Memory entries: ${count}${hint ? ` | ${hint}` : ""}`);
    }
  } catch (error) {
    reportIssue(
      "PHX-MEM-101",
      "memory_check_failed",
      error?.message || String(error),
      {},
      "warn",
      true
    );
    toast("Memory check failed. Attempting reinject...", "warn");
    try {
      await api.memoryReload();
      toast("Memory reinjected.");
    } catch {
      reportIssue("PHX-MEM-102", "memory_reinject_failed", "", {}, "error", true);
      // ignore
    }
  }
}

async function openLogs() {
  try {
    await api.logsOpen();
    toast("Logs folder opened.");
  } catch (error) {
    reportIssue("PHX-UI-201", "logs_open_failed", error?.message || String(error), {}, "warn", true);
    toast("Logs open failed.", "warn");
  }
}

async function openFileBrowser() {
  try {
    await api.filesOpen({});
    toast("File browser opened.");
  } catch (error) {
    reportIssue(
      "PHX-UI-202",
      "file_browser_failed",
      error?.message || String(error),
      {},
      "warn",
      true
    );
    toast("File browser failed.", "warn");
  }
}

function formatPerfValue(value, suffix = "", digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "--";
  }
  return `${num.toFixed(digits)}${suffix}`;
}

function formatPerfMs(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return `${value.toFixed(1)}ms`;
}

function buildPerfReport(snapshot) {
  const lines = [];
  lines.push("Phoenix-15 Performance Snapshot");
  lines.push(`Time: ${new Date().toLocaleString()}`);
  lines.push("");
  lines.push("System:");
  if (snapshot && snapshot.system) {
    lines.push(`- CPU: ${formatPerfValue(snapshot.system.cpu_percent, "%")}`);
    if (Array.isArray(snapshot.system.cpu_per_core) && snapshot.system.cpu_per_core.length) {
      lines.push(
        `- CPU Cores: ${snapshot.system.cpu_per_core
          .map((val) => formatPerfValue(val, "%", 0))
          .join(", ")}`
      );
    }
    const memUsed = snapshot.system.memory_used_mb;
    const memTotal = snapshot.system.memory_total_mb;
    const memAvail = snapshot.system.memory_available_mb;
    if (memTotal) {
      lines.push(
        `- MEM: ${formatPerfValue(snapshot.system.memory_percent, "%")} (${formatPerfValue(
          memUsed,
          "MB"
        )} / ${formatPerfValue(memTotal, "MB")}, avail ${formatPerfValue(memAvail, "MB")})`
      );
    } else {
      lines.push(`- MEM: ${formatPerfValue(snapshot.system.memory_percent, "%")}`);
    }
    if (snapshot.system.swap_total_mb) {
      lines.push(
        `- SWAP: ${formatPerfValue(snapshot.system.swap_percent, "%")} (${formatPerfValue(
          snapshot.system.swap_used_mb,
          "MB"
        )} / ${formatPerfValue(snapshot.system.swap_total_mb, "MB")})`
      );
    }
    lines.push(`- GPU: ${formatPerfValue(snapshot.system.gpu_percent, "%")}`);
    if (Array.isArray(snapshot.system.gpus) && snapshot.system.gpus.length) {
      snapshot.system.gpus.forEach((gpu, idx) => {
        const name = gpu.name || `GPU ${idx}`;
        const mem =
          gpu.mem_total_mb !== undefined
            ? ` mem=${formatPerfValue(gpu.mem_used_mb, "MB")}/${formatPerfValue(
                gpu.mem_total_mb,
                "MB"
              )}`
            : "";
        const temp =
          gpu.temp_c !== undefined && gpu.temp_c !== null
            ? ` temp=${formatPerfValue(gpu.temp_c, "C", 0)}`
            : "";
        lines.push(
          `- GPU${idx}: ${name} load=${formatPerfValue(gpu.load_percent, "%")}${mem}${temp}`
        );
      });
    }
    lines.push(`- Uptime: ${formatPerfValue(snapshot.system.uptime_seconds, "s", 0)}`);
    lines.push(`- Processes: ${snapshot.system.processes ?? "--"}`);
    if (snapshot.system.disk_usage) {
      lines.push(
        `- Disk: ${formatPerfValue(snapshot.system.disk_usage.percent, "%")} (${formatPerfValue(
          snapshot.system.disk_usage.used_mb,
          "MB"
        )} / ${formatPerfValue(snapshot.system.disk_usage.total_mb, "MB")}, free ${formatPerfValue(
          snapshot.system.disk_usage.free_mb,
          "MB"
        )} @ ${snapshot.system.disk_usage.root || "--"})`
      );
    }
    if (snapshot.system.disk_io) {
      lines.push(
        `- Disk IO: read=${formatPerfValue(
          snapshot.system.disk_io.read_mb,
          "MB"
        )} write=${formatPerfValue(snapshot.system.disk_io.write_mb, "MB")} ops=${snapshot.system.disk_io.read_count ?? "--"}/${snapshot.system.disk_io.write_count ?? "--"}`
      );
    }
  } else {
    lines.push("- System metrics unavailable.");
  }

  const perfMem = performance && performance.memory ? performance.memory : null;
  if (perfMem) {
    const used = perfMem.usedJSHeapSize / (1024 * 1024);
    const total = perfMem.totalJSHeapSize / (1024 * 1024);
    const limit = perfMem.jsHeapSizeLimit / (1024 * 1024);
    lines.push(`- UI Heap: ${formatPerfValue(used, "MB")} / ${formatPerfValue(total, "MB")} (limit ${formatPerfValue(limit, "MB")})`);
  }

  lines.push("");
  lines.push("Processes:");
  if (snapshot && Array.isArray(snapshot.processes) && snapshot.processes.length) {
    snapshot.processes.forEach((proc) => {
      const role = proc.role ? `[${proc.role}]` : "[proc]";
      lines.push(
        `- ${role} ${proc.name} pid=${proc.pid} cpu=${formatPerfValue(proc.cpu_percent, "%")} mem=${formatPerfValue(proc.rss_mb, "MB")} threads=${proc.threads ?? "--"}`
      );
    });
  } else {
    lines.push("- No process data.");
  }

  lines.push("");
  lines.push("Top CPU:");
  if (snapshot && Array.isArray(snapshot.top_cpu) && snapshot.top_cpu.length) {
    snapshot.top_cpu.forEach((proc) => {
      lines.push(
        `- ${proc.name} pid=${proc.pid} cpu=${formatPerfValue(proc.cpu_percent, "%")} mem=${formatPerfValue(
          proc.rss_mb,
          "MB"
        )}`
      );
    });
  } else {
    lines.push("- No CPU ranking data.");
  }

  lines.push("");
  lines.push("Top Memory:");
  if (snapshot && Array.isArray(snapshot.top_memory) && snapshot.top_memory.length) {
    snapshot.top_memory.forEach((proc) => {
      lines.push(
        `- ${proc.name} pid=${proc.pid} mem=${formatPerfValue(proc.rss_mb, "MB")} cpu=${formatPerfValue(
          proc.cpu_percent,
          "%"
        )}`
      );
    });
  } else {
    lines.push("- No memory ranking data.");
  }

  lines.push("");
  lines.push("UI State:");
  lines.push(`- awake=${state.awake} locked=${state.locked} loading=${state.loading} hidden=${state.uiHidden}`);
  lines.push(
    `- perfFocus=${state.settings.performanceFocusEnabled} autoPerf=${state.autoPerfActive} profile=${snapshot?.profile || "--"}`
  );
  lines.push(`- history=${state.history.length} panels=${document.querySelectorAll(".panel.floating").length}`);

  const orb = state.perfStats.orb || {};
  lines.push("");
  lines.push("Orb:");
  lines.push(
    `- state=${state.orbState} fps=${formatPerfValue(orb.fps, "", 0)} avgFrame=${formatPerfMs(orb.avgFrameMs)} dots=${orb.dotCount} glyphs=${orb.glyphCount}`
  );

  lines.push("");
  lines.push("Loops:");
  const loops = state.perfStats.loops || {};
  const loopKeys = Object.keys({ ...PERF_LOOP_INTERVALS, ...loops });
  loopKeys.forEach((key) => {
    const entry = loops[key] || {};
    const interval = PERF_LOOP_INTERVALS[key];
    const lastAgo = entry.lastAt ? Math.round((Date.now() - entry.lastAt) / 1000) : null;
    lines.push(
      `- ${key}: avg=${formatPerfMs(entry.avgMs)} last=${formatPerfMs(entry.lastMs)} lastAgo=${lastAgo ?? "--"}s interval=${interval ? `${interval.base}/${interval.slow}ms` : "--"}`
    );
  });

  lines.push("");
  lines.push("Modules:");
  lines.push(
    `- Audio Lab: devicesLoaded=${state.audioDevicesLoaded} eqBands=${state.audioEq.bands.length} sessions=${state.audioSessions.length} target=${state.audioEqTarget}`
  );
  lines.push(
    `- Frequency Hub: analyzing=${state.freqAnalyzing} file=${state.freqFile?.name || "--"} peaks=${state.freqAnalysis?.peaks?.length || 0}`
  );
  lines.push(
    `- Spotify: authorized=${state.spotify.authorized} playing=${state.spotify.isPlaying} track=${state.spotify.track || "--"}`
  );
  lines.push(
    `- Remote: enabled=${state.settings.remoteUiEnabled} tunnel=${state.remoteTunnel.running} url=${state.remoteTunnel.url || "--"}`
  );
  lines.push(`- USB: manualOnly localBoot=${state.settings.usbLocalBootEnabled}`);
  lines.push(`- Desktop View: enabled=${state.settings.desktopViewEnabled}`);

  return lines.join("\n");
}

async function refreshPerfReport(options = {}) {
  const report = $("perf-report");
  if (!report) {
    return;
  }
  report.textContent = "Collecting performance snapshot...";
  let snapshot = null;
  try {
    snapshot = await api.perfSnapshot();
  } catch (error) {
    reportIssue(
      "PHX-PERF-001",
      "perf_snapshot_failed",
      error?.message || String(error),
      {},
      "warn",
      true
    );
  }
  const output = buildPerfReport(snapshot);
  state.perfStats.lastReport = output;
  report.textContent = output;
  if (options.log) {
    fireAndForget(
      api.perfLog?.({
        report: output,
        source: options.source || "ui",
        snapshot,
      })
    );
  }
}

async function refreshAudioDevices() {
  const inputSelect = $("audio-input");
  const outputSelect = $("audio-output");
  if (!inputSelect || !outputSelect) {
    return;
  }
  try {
    const data = await api.audioDevices();
    const devices = data.devices || [];
    const selectedInput = inputSelect.value;
    const selectedOutput = outputSelect.value;
    inputSelect.innerHTML = "";
    outputSelect.innerHTML = "";
    devices.forEach((device) => {
      const label = `${device.name || "Device"} (${device.hostapi_name || "?"})`;
      if (device.max_input_channels > 0) {
        const opt = document.createElement("option");
        opt.value = String(device.id);
        opt.textContent = label;
        inputSelect.appendChild(opt);
      }
      if (device.max_output_channels > 0) {
        const opt = document.createElement("option");
        opt.value = String(device.id);
        opt.textContent = label;
        outputSelect.appendChild(opt);
      }
    });
    if (selectedInput && inputSelect.querySelector(`option[value="${selectedInput}"]`)) {
      inputSelect.value = selectedInput;
    } else if (data.default_input !== undefined && data.default_input !== null) {
      inputSelect.value = String(data.default_input);
    }
    if (selectedOutput && outputSelect.querySelector(`option[value="${selectedOutput}"]`)) {
      outputSelect.value = selectedOutput;
    } else if (data.default_output !== undefined && data.default_output !== null) {
      outputSelect.value = String(data.default_output);
    }
    state.audioDevicesLoaded = true;
    toast("Audio devices refreshed.");
    refreshAudioSystemMix();
    refreshAudioEqEngine();
  } catch (error) {
    reportIssue(
      "PHX-AUD-101",
      "audio_devices_unavailable",
      error?.message || String(error),
      {},
      "warn",
      true
    );
    toast("Audio devices unavailable.", "warn");
  }
}

async function applyAudioDevices() {
  const inputSelect = $("audio-input");
  const outputSelect = $("audio-output");
  if (!inputSelect || !outputSelect) {
    return;
  }
  try {
    await api.audioActiveDevice({
      input: inputSelect.value ? Number(inputSelect.value) : null,
      output: outputSelect.value ? Number(outputSelect.value) : null,
    });
    toast("Audio devices applied.");
    refreshAudioSystemMix();
  } catch (error) {
    reportIssue(
      "PHX-AUD-102",
      "audio_device_update_failed",
      error?.message || String(error),
      {},
      "warn",
      true
    );
    toast("Audio device update failed.", "warn");
  }
}

function formatEqBandLabel(freq) {
  if (!freq) {
    return "--";
  }
  if (freq >= 1000) {
    const val = freq / 1000;
    return `${val.toFixed(val >= 10 ? 0 : 1)}k`;
  }
  return String(freq);
}

function formatDb(value) {
  const num = Number(value) || 0;
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(1)} dB`;
}

function formatHz(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) {
    return "--";
  }
  if (num >= 1000) {
    const val = num / 1000;
    return `${val.toFixed(val >= 10 ? 1 : 2)} kHz`;
  }
  return `${num.toFixed(num >= 100 ? 0 : 1)} Hz`;
}

function formatSampleRate(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) {
    return "--";
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)} kHz`;
  }
  return `${Math.round(num)} Hz`;
}

function formatDuration(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) {
    return "--";
  }
  if (num >= 60) {
    const mins = Math.floor(num / 60);
    const secs = String(Math.floor(num % 60)).padStart(2, "0");
    return `${mins}:${secs}`;
  }
  return `${num.toFixed(num >= 10 ? 1 : 2)}s`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function hashString(text) {
  const str = String(text || "");
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function bucketFrequency(hz) {
  const num = Number(hz);
  if (!Number.isFinite(num) || num <= 0) {
    return null;
  }
  return Math.round(num / 5) * 5;
}

function getEmotionBandForFrequency(hz) {
  const num = Number(hz);
  if (!Number.isFinite(num)) {
    return ORB_EMOTION_BANDS[0];
  }
  for (const band of ORB_EMOTION_BANDS) {
    const [low, high] = band.range;
    if (num >= low && num <= high) {
      return band;
    }
  }
  return ORB_EMOTION_BANDS[ORB_EMOTION_BANDS.length - 1];
}

function selectEmotionBandForState(stateName, text) {
  const baseIndex =
    {
      dormant: 0,
      listening: 1,
      thinking: 2,
      speaking: 3,
    }[stateName] ?? 1;
  const length = String(text || "").length;
  const lengthBoost = length > 280 ? 2 : length > 140 ? 1 : 0;
  const energyBoost = state.orbEnergy > 0.8 ? 2 : state.orbEnergy > 0.6 ? 1 : 0;
  const actionBoost = state.orbAction ? 1 : 0;
  const boost = Math.max(lengthBoost, energyBoost, actionBoost);
  const index = Math.min(ORB_EMOTION_BANDS.length - 1, baseIndex + boost);
  return ORB_EMOTION_BANDS[index];
}

function deriveConsciousnessFrequency(text) {
  const band = selectEmotionBandForState(state.orbState, text);
  const [low, high] = band.range;
  const span = Math.max(1, high - low);
  const seed = hashString(`${state.orbState}|${state.orbThought}|${text || ""}`);
  const offset = seed % (span + 1);
  const energyShift = Math.round(state.orbEnergy * 8);
  const hz = clampNumber(low + offset + energyShift, low, high, low);
  const bucket = bucketFrequency(hz);
  return { hz, bucket, band };
}

function truncateText(text, max = 140) {
  const cleaned = String(text || "").replace(/\s+/g, " ").trim();
  if (cleaned.length <= max) {
    return cleaned;
  }
  return `${cleaned.slice(0, Math.max(0, max - 3))}...`;
}

function updateOrbEmotionUI() {
  safeText("orb-emotion-line", `Emotion: ${state.orbEmotion || "Unknown"}`);
  safeText("orb-frequency-line", `Frequency: ${formatHz(state.orbFrequencyHz)}`);
}

function buildEmotionContext({ reply, userText, band, heartbeatHz, stateName }) {
  const lines = [];
  if (stateName) {
    lines.push(`State: ${stateName}`);
  }
  if (Number.isFinite(heartbeatHz)) {
    lines.push(`Heartbeat: ${heartbeatHz.toFixed(2)} Hz`);
  }
  if (band) {
    const [low, high] = band.range;
    lines.push(`Band: ${low}-${high} Hz (${band.palette})`);
  }
  if (userText) {
    lines.push(`User prompt: ${truncateText(userText, 120)}`);
  }
  if (reply) {
    lines.push(`AI reply: ${truncateText(reply, 160)}`);
  }
  return lines.join("\n");
}

function updateEmotionPromptUI() {
  safeText("emotion-frequency", formatHz(state.emotionPrompt.hz));
  safeText("emotion-heartbeat", formatHz(state.orbHeartbeatHz));
  safeText("emotion-state", state.emotionPrompt.state || state.orbState || "--");
  safeText(
    "emotion-band",
    state.emotionPrompt.bandRange || (state.emotionPrompt.palette || "gray")
  );
  safeText("emotion-context", state.emotionPrompt.context || "");
  const input = $("emotion-input");
  if (input) {
    input.value = state.orbEmotion && state.orbEmotion !== "Unknown" ? state.orbEmotion : "";
  }
}

function openEmotionPrompt(payload) {
  if (!state.settings.emotionPromptEnabled) {
    return;
  }
  state.emotionPrompt = {
    open: true,
    hz: payload.hz,
    bucket: payload.bucket,
    palette: payload.palette || "gray",
    bandRange: payload.bandRange || "",
    state: payload.stateName || "",
    reason: payload.reason || "",
    context: payload.context || "",
  };
  state.emotionPromptLastAt = Date.now();
  state.lastEmotionBucket = payload.bucket ? String(payload.bucket) : null;
  updateEmotionPromptUI();
  applyPanelVisibility();
  const input = $("emotion-input");
  if (input) {
    input.focus();
  }
}

function closeEmotionPrompt() {
  state.emotionPrompt.open = false;
  applyPanelVisibility();
}

function snoozeEmotionPrompt() {
  const key = state.emotionPrompt.bucket ? String(state.emotionPrompt.bucket) : "";
  if (key) {
    state.emotionPromptSnooze[key] = Date.now() + EMOTION_PROMPT_SNOOZE_MS;
  }
  closeEmotionPrompt();
}

async function saveEmotionPrompt() {
  const input = $("emotion-input");
  const label = input ? input.value.trim() : "";
  const bucket = state.emotionPrompt.bucket;
  if (!label || !bucket) {
    toast("Enter an emotion label first.", "warn");
    return;
  }
  const key = String(bucket);
  state.emotionMap[key] = label;
  saveOrbEmotionMap(state.activeUserId, state.emotionMap);
  state.orbEmotion = label;
  updateOrbEmotionUI();
  try {
    await api.audioEmotionTag({ hz: bucket, emotion: label });
  } catch (error) {
    reportIssue(
      "PHX-EMO-201",
      "emotion_tag_failed",
      error?.message || String(error),
      { bucket, label },
      "warn",
      true
    );
    toast("Saved locally. Backend tag failed.", "warn");
  }
  closeEmotionPrompt();
  toast("Emotion saved.", "info");
}

function shouldPromptEmotion(bucket) {
  if (!bucket) {
    return false;
  }
  if (!state.settings.emotionPromptEnabled || state.locked || !state.awake) {
    return false;
  }
  const key = String(bucket);
  if (state.emotionMap && state.emotionMap[key]) {
    return false;
  }
  if (state.emotionPrompt.open) {
    return false;
  }
  const now = Date.now();
  if (now - state.emotionPromptLastAt < EMOTION_PROMPT_COOLDOWN_MS) {
    return false;
  }
  if (state.emotionPromptSnooze[key] && now < state.emotionPromptSnooze[key]) {
    return false;
  }
  return true;
}

function updateConsciousnessFromReply({ reply, userText }) {
  const derived = deriveConsciousnessFrequency(reply || "");
  state.orbFrequencyHz = derived.hz;
  const bucketKey = derived.bucket ? String(derived.bucket) : "";
  const storedEmotion = bucketKey ? state.emotionMap[bucketKey] : "";
  state.orbEmotion = storedEmotion || "Unknown";
  updateOrbEmotionUI();
  const heartbeatHz = state.orbHeartbeatHz || getHeartbeatHz();
  if (!shouldPromptEmotion(derived.bucket)) {
    return;
  }
  const bandRange = derived.band ? `${derived.band.range[0]}-${derived.band.range[1]} Hz` : "";
  const context = buildEmotionContext({
    reply,
    userText,
    band: derived.band,
    heartbeatHz,
    stateName: state.orbState,
  });
  openEmotionPrompt({
    hz: derived.hz,
    bucket: derived.bucket,
    palette: derived.band?.palette || "gray",
    bandRange,
    stateName: state.orbState,
    context,
  });
}

function renderLoadingChecks(checks) {
  const list = $("loading-checks");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  if (!Array.isArray(checks) || checks.length === 0) {
    const empty = document.createElement("div");
    empty.className = "loading-check loading-check-muted";
    empty.textContent = "Awaiting system reports...";
    list.appendChild(empty);
    return;
  }
  checks.forEach((check) => {
    const row = document.createElement("div");
    const ok = Boolean(check.ok);
    row.className = `loading-check ${ok ? "loading-check-ok" : "loading-check-fail"}`;
    const label = document.createElement("span");
    label.textContent = check.module || "module";
    const code = document.createElement("span");
    code.textContent = ok ? "OK" : check.code || "FAIL";
    row.appendChild(label);
    row.appendChild(code);
    if (check.detail) {
      row.title = check.detail;
    }
    list.appendChild(row);
  });
}

function updateLoadingProgress(checks) {
  const bar = $("loading-bar");
  if (!bar) {
    return;
  }
  const total = Array.isArray(checks) ? checks.length : 0;
  if (!total) {
    bar.style.width = "20%";
    return;
  }
  const okCount = checks.filter((check) => check && check.ok).length;
  const pct = Math.max(10, Math.round((okCount / total) * 100));
  bar.style.width = `${pct}%`;
}

function renderLoadingError(error) {
  const panel = $("loading-error");
  const body = $("loading-error-body");
  if (!panel || !body) {
    return;
  }
  if (!error) {
    panel.classList.add("hidden");
    body.textContent = "";
    return;
  }
  panel.classList.remove("hidden");
  const lines = Array.isArray(error.lines) ? error.lines : [];
  const summary = error.summary ? `${error.summary}\n` : "";
  body.textContent = `${summary}${lines.join("\n")}`.trim();
}

async function runStartupChecks() {
  state.loading = true;
  state.bootError = null;
  applyLoadingState();
  safeText("loading-status", "Initializing systems...");
  const checks = [];
  renderLoadingChecks(checks);
  updateLoadingProgress(checks);
  renderLoadingError(null);
  try {
    const pushCheck = (entry) => {
      checks.push(entry);
      state.bootChecks = checks.slice();
      renderLoadingChecks(checks);
      updateLoadingProgress(checks);
    };

    const retryStep = async (label, fn, opts = {}) => {
      const attempts = Math.max(1, Number(opts.attempts || 1));
      const delayMs = Math.max(0, Number(opts.delayMs || 0));
      let lastError = null;
      for (let i = 0; i < attempts; i += 1) {
        try {
          return await fn();
        } catch (error) {
          lastError = error;
          if (i < attempts - 1 && delayMs) {
            safeText("loading-status", `${label} (retry ${i + 2}/${attempts})...`);
            await delay(delayMs);
          }
        }
      }
      throw lastError;
    };

    safeText("loading-status", "Checking backend...");
    let backendOk = false;
    try {
      const ready = await retryStep(
        "Checking backend",
        () =>
          withTimeout(
            ensureBackendOnline().then((ok) => {
              if (ok) {
                return true;
              }
              throw new Error("backend offline");
            }),
            12000,
            "backend timeout"
          ),
        { attempts: 2, delayMs: 1000 }
      );
      if (ready) {
        pushCheck({ module: "backend", ok: true, code: "PHX-NET-000", detail: "" });
        backendOk = true;
      }
    } catch (error) {
      pushCheck({
        module: "backend",
        ok: false,
        code: "PHX-NET-101",
        detail: error?.message || String(error),
      });
    }
    if (backendOk) {
      await delay(500);
    }

    safeText("loading-status", "Loading settings...");
    try {
      const data = await retryStep(
        "Loading settings",
        async () => {
          await ensureBackendOnline();
          return withTimeout(api.settingsGet(20000), 22000, "settings timeout");
        },
        { attempts: 3, delayMs: 1200 }
      );
      if (data && !state.localSettingsLoaded) {
        state.settings = { ...state.settings, ...data };
        state.settings.theme = normalizeTheme(state.settings.theme);
      }
      pushCheck({ module: "settings", ok: true, code: "PHX-SET-000", detail: "" });
    } catch (error) {
      const baseHint = api && api.baseUrl ? ` base=${api.baseUrl}` : "";
      pushCheck({
        module: "settings",
        ok: false,
        code: "PHX-SET-001",
        detail: `${error?.message || String(error)}${baseHint}`,
      });
    }

    safeText("loading-status", "Loading audio settings...");
    try {
      await retryStep(
        "Loading audio settings",
        async () => {
          await ensureBackendOnline();
          const ready = await waitForAudioHealth(30000);
          if (!ready) {
            throw new Error("audio health timeout");
          }
          return withTimeout(
            loadAudioSettings({ throwOnFailure: true, timeoutMs: 30000 }),
            32000,
            "audio timeout"
          );
        },
        { attempts: 3, delayMs: 1500 }
      );
      pushCheck({ module: "audio_settings", ok: true, code: "PHX-AUD-010", detail: "" });
    } catch (error) {
      const baseHint = api && api.baseUrl ? ` base=${api.baseUrl}` : "";
      pushCheck({
        module: "audio_settings",
        ok: false,
        code: "PHX-AUD-011",
        detail: `${error?.message || String(error)}${baseHint}`,
      });
    }

    syncSettingsUI();
    saveSettings();
    initLogin();
    refreshDisplayLease();

    safeText("loading-status", "Running self-check...");
    try {
      const selfcheckTimeout = 45000;
      const data = await retryStep(
        "Running self-check",
        () =>
          withTimeout(
            api.selfcheck(selfcheckTimeout),
            selfcheckTimeout + 3000,
            "selfcheck timeout"
          ),
        { attempts: 3, delayMs: 2000 }
      );
      if (data && Array.isArray(data.checks)) {
        data.checks.forEach((item) => pushCheck(item));
      }
    } catch (error) {
      pushCheck({
        module: "selfcheck",
        ok: false,
        code: "PHX-SYS-999",
        detail: error?.message || String(error),
      });
    }

    const blocking = checks.filter(
      (check) => check && !check.ok && String(check.module || "") !== "ollama"
    );
    if (blocking.length === 0) {
      safeText("loading-status", "Systems ready.");
      state.bootError = null;
      renderLoadingError(null);
      state.loading = false;
      if (!state.settings.loginEnabled) {
        initPostLogin();
        scheduleUserHydration();
        startLoops();
      }
    } else {
      safeText("loading-status", "Systems reported issues.");
      const lines = blocking.map(
        (item) => `- ${item.module || "module"}: ${item.code || "PHX-UNK-000"} ${item.detail || ""}`.trim()
      );
      state.bootError = {
        summary: "Boot checks reported issues.",
        lines,
      };
      renderLoadingError(state.bootError);
      reportIssue(
        "PHX-BOOT-001",
        "boot_checks_failed",
        lines.join(" | "),
        {},
        "error",
        true
      );
    }
  } finally {
    applyLoadingState();
    applyLockState();
  }
}

function normalizeEqValues(values, bands) {
  const count = Array.isArray(bands) ? bands.length : 0;
  const normalized = Array.isArray(values) ? values.slice(0, count) : [];
  while (normalized.length < count) {
    normalized.push(0);
  }
  return normalized.map((value) => clampNumber(value, -12, 12, 0));
}

function nearestBandIndex(bands, freq) {
  if (!Array.isArray(bands) || bands.length === 0) {
    return -1;
  }
  let bestIndex = 0;
  let bestDelta = Number.POSITIVE_INFINITY;
  bands.forEach((band, idx) => {
    const delta = Math.abs(Number(band) - freq);
    if (delta < bestDelta) {
      bestDelta = delta;
      bestIndex = idx;
    }
  });
  return bestIndex;
}

function applyProfilePreferences(values, bands, prefs) {
  const eqValues = normalizeEqValues(values, bands);
  const prefValues = normalizeAudioProfilePrefs(prefs);
  const tuning = [
    { key: "bass", targets: [31, 62, 125], scale: 0.25 },
    { key: "warmth", targets: [125, 250, 500], scale: 0.2 },
    { key: "clarity", targets: [2000, 4000], scale: 0.2 },
    { key: "air", targets: [8000, 16000], scale: 0.25 },
  ];
  tuning.forEach((profile) => {
    const bias = (prefValues[profile.key] || 0) * profile.scale;
    if (!bias) {
      return;
    }
    profile.targets.forEach((freq) => {
      const idx = nearestBandIndex(bands, freq);
      if (idx < 0) {
        return;
      }
      eqValues[idx] = clampNumber(eqValues[idx] + bias, -12, 12, eqValues[idx]);
    });
  });
  return eqValues;
}

function updateSuggestedEqForTarget(target) {
  const bands = state.audioEq.bands && state.audioEq.bands.length
    ? state.audioEq.bands
    : AUDIO_HEARING_DEFAULT_BANDS;
  const base = state.audioSuggestedEqBase[target] || [];
  if (!base.length) {
    state.audioSuggestedEq[target] = [];
    return;
  }
  state.audioSuggestedEq[target] = applyProfilePreferences(base, bands, state.audioProfilePrefs);
}

function refreshSuggestedEqFromPrefs() {
  updateSuggestedEqForTarget("output");
  updateSuggestedEqForTarget("input");
}

function renderAudioEqList() {
  const list = $("audio-eq-list");
  if (!list) {
    return;
  }
  const bands = state.audioEq.bands || [];
  const target = state.audioEqTarget || "output";
  const values = normalizeEqValues(state.audioEq[target], bands);
  state.audioEq[target] = values;
  list.innerHTML = "";
  if (bands.length === 0) {
    list.textContent = "EQ unavailable.";
    return;
  }
  bands.forEach((freq, index) => {
    const band = document.createElement("div");
    band.className = "audio-eq-band";
    const valueEl = document.createElement("span");
    valueEl.className = "audio-eq-value";
    valueEl.textContent = formatDb(values[index]);
    const sliderWrap = document.createElement("div");
    sliderWrap.className = "audio-eq-slider-wrap";
    const slider = document.createElement("input");
    slider.className = "audio-eq-slider";
    slider.type = "range";
    slider.min = "-12";
    slider.max = "12";
    slider.step = "0.5";
    slider.value = String(values[index]);
    const label = document.createElement("span");
    label.className = "audio-eq-label";
    label.textContent = formatEqBandLabel(freq);
    slider.addEventListener("input", () => {
      const val = Number(slider.value);
      state.audioEq[target][index] = val;
      valueEl.textContent = formatDb(val);
    });
    slider.addEventListener("change", () => {
      api.audioEqSet({ target, bands: state.audioEq[target] }).catch(() => {});
    });
    sliderWrap.appendChild(slider);
    band.appendChild(valueEl);
    band.appendChild(sliderWrap);
    band.appendChild(label);
    list.appendChild(band);
  });
}

async function refreshAudioEq() {
  try {
    const data = await api.audioEq();
    const bands = Array.isArray(data.bands) ? data.bands : [];
    state.audioEq.bands = bands;
    state.audioEq.input = normalizeEqValues(data.input, bands);
    state.audioEq.output = normalizeEqValues(data.output, bands);
    renderAudioEqList();
    refreshSuggestedEqFromPrefs();
  } catch (error) {
    const list = $("audio-eq-list");
    if (list) {
      list.textContent = "EQ unavailable.";
    }
    reportIssue("PHX-AUD-110", "audio_eq_unavailable", error?.message || String(error), {}, "warn", true);
  }
}

async function refreshAudioEqEngine() {
  const statusEl = $("audio-eq-status");
  const detailEl = $("audio-eq-status-detail");
  const configInput = $("audio-eq-config-path");
  if (!statusEl) {
    return;
  }
  try {
    const data = await api.audioEqEngine();
    const status = data.status || {};
    if (status.available) {
      const engine = status.engine || "unknown";
      statusEl.textContent = `EQ Engine: ${engine}`;
    } else {
      statusEl.textContent = "EQ Engine: unavailable";
    }
    if (configInput && !configInput.value && status.config_path) {
      configInput.placeholder = status.config_path;
    }
    if (detailEl) {
      const detail = [];
      if (status.config_path) {
        detail.push(`Config: ${status.config_path}`);
      }
      if (status.detail) {
        detail.push(status.detail);
      }
      if (status.error) {
        detail.push(status.error);
      }
      detailEl.textContent = detail.join(" | ");
    }
  } catch (error) {
    statusEl.textContent = "EQ Engine: unavailable";
    if (detailEl) {
      detailEl.textContent = "";
    }
    reportIssue("PHX-AUD-111", "eq_engine_unavailable", error?.message || String(error), {}, "warn", true);
  }
}

async function applyAudioEqSystem() {
  try {
    const target = state.audioEqTarget || "output";
    const bands = state.audioEq[target] || [];
    const data = await api.audioEqApply({ target, bands });
    const status = (data && data.status) || {};
    if (status.applied) {
      toast("EQ applied to system.");
    } else if (status.error) {
      toast(status.error, "warn");
    } else if (status.detail) {
      toast(status.detail, "warn");
    } else {
      toast("EQ engine unavailable.", "warn");
    }
    refreshAudioEqEngine();
  } catch (error) {
    toast("EQ apply failed.", "warn");
  }
}

function resetAudioEqFlat() {
  const target = state.audioEqTarget || "output";
  const bands = state.audioEq.bands || [];
  state.audioEq[target] = normalizeEqValues([], bands);
  renderAudioEqList();
  api.audioEqSet({ target, bands: state.audioEq[target] }).catch(() => {});
}

function buildSpotifyEmbedUrl(raw) {
  const input = String(raw || "").trim();
  if (!input) {
    return "";
  }
  if (input.includes("open.spotify.com/embed/")) {
    return ensureSpotifyTheme(input);
  }
  const uriMatch = input.match(
    /spotify:(track|album|playlist|artist|episode|show):([A-Za-z0-9]+)/i
  );
  if (uriMatch) {
    return ensureSpotifyTheme(
      `https://open.spotify.com/embed/${uriMatch[1]}/${uriMatch[2]}`
    );
  }
  const urlMatch = input.match(
    /open\.spotify\.com\/(track|album|playlist|artist|episode|show)\/([A-Za-z0-9]+)/i
  );
  if (urlMatch) {
    return ensureSpotifyTheme(
      `https://open.spotify.com/embed/${urlMatch[1]}/${urlMatch[2]}`
    );
  }
  return input;
}

function ensureSpotifyTheme(url) {
  if (!url.includes("open.spotify.com/embed/")) {
    return url;
  }
  if (/[?&]theme=/.test(url)) {
    return url;
  }
  const joiner = url.includes("?") ? "&" : "?";
  return `${url}${joiner}theme=0`;
}

function renderAudioMedia() {
  const iframe = $("audio-spotify-embed");
  const empty = $("audio-media-empty");
  if (!iframe) {
    return;
  }
  const source = state.audioSettings.mediaSource || audioDefaults.mediaSource;
  if (source !== "spotify") {
    iframe.removeAttribute("src");
    iframe.classList.add("hidden");
    if (empty) {
      empty.textContent = "Media player disabled.";
      empty.classList.remove("hidden");
    }
    return;
  }
  const embedUrl = buildSpotifyEmbedUrl(state.audioSettings.spotifyUrl || "");
  if (!embedUrl) {
    iframe.removeAttribute("src");
    iframe.classList.add("hidden");
    if (empty) {
      empty.textContent = "Paste a Spotify link to load the player.";
      empty.classList.remove("hidden");
    }
    return;
  }
  if (iframe.getAttribute("src") !== embedUrl) {
    iframe.setAttribute("src", embedUrl);
  }
  iframe.classList.remove("hidden");
  if (empty) {
    empty.classList.add("hidden");
  }
}

function applySpotifyUrl() {
  const input = $("audio-spotify-url");
  if (!input) {
    return;
  }
  state.audioSettings.spotifyUrl = input.value.trim();
  saveAudioSettings();
  renderAudioMedia();
}

function clearSpotifyUrl() {
  const input = $("audio-spotify-url");
  state.audioSettings.spotifyUrl = "";
  if (input) {
    input.value = "";
  }
  saveAudioSettings();
  renderAudioMedia();
}

function formatSpotifyArtists(item) {
  const artists = item && Array.isArray(item.artists) ? item.artists : [];
  return artists.map((artist) => artist.name).filter(Boolean).join(", ");
}

function formatSpotifyTrack(item) {
  if (!item) {
    return "";
  }
  const title = item.name || "";
  const artists = formatSpotifyArtists(item);
  if (title && artists) {
    return `${title} — ${artists}`;
  }
  return title || artists || "";
}

function setSpotifyControlsEnabled(enabled) {
  const ids = [
    "spotify-prev",
    "spotify-play",
    "spotify-pause",
    "spotify-next",
    "spotify-device",
    "spotify-transfer",
    "spotify-volume",
    "spotify-shuffle",
    "spotify-repeat",
    "audio-spotify-play",
  ];
  ids.forEach((id) => {
    const el = $(id);
    if (el) {
      el.disabled = !enabled;
    }
  });
  const connect = $("spotify-connect");
  if (connect) {
    connect.disabled = enabled;
  }
  const disconnect = $("spotify-disconnect");
  if (disconnect) {
    disconnect.disabled = !enabled;
  }
}

function renderSpotifyDevices(devices) {
  const select = $("spotify-device");
  if (!select) {
    return;
  }
  select.innerHTML = "";
  const list = Array.isArray(devices) ? devices : [];
  list.forEach((device) => {
    const opt = document.createElement("option");
    opt.value = device.id;
    opt.textContent = device.name || "Device";
    select.appendChild(opt);
  });
  const active = list.find((device) => device.is_active) || list[0];
  if (active) {
    select.value = active.id;
  }
}

async function refreshSpotifyDevices() {
  try {
    const data = await api.spotifyDevices();
    const devices = Array.isArray(data.devices) ? data.devices : [];
    state.spotify.devices = devices;
    state.spotify.activeDeviceId = devices.find((device) => device.is_active)?.id || "";
    renderSpotifyDevices(devices);
    state.spotifyDevicesAt = Date.now();
  } catch (error) {
    // ignore
  }
}

async function refreshSpotifyStatus() {
  const statusEl = $("spotify-status");
  const trackEl = $("spotify-track");
  try {
    const data = await api.spotifyStatus();
    if (!data || !data.authorized) {
      state.spotify = { ...state.spotify, authorized: false, isPlaying: false, track: "" };
      if (statusEl) {
        statusEl.textContent = "Spotify: disconnected";
      }
      if (trackEl) {
        trackEl.textContent = "No active playback.";
      }
      renderSpotifyDevices([]);
      setSpotifyControlsEnabled(false);
      return;
    }
    const profile = data.profile || {};
    const player = data.player || {};
    const item = player.item || null;
    const track = formatSpotifyTrack(item);
    const user = profile.display_name || profile.id || "";
    state.spotify.authorized = true;
    state.spotify.user = user;
    state.spotify.track = track;
    state.spotify.isPlaying = Boolean(player.is_playing);
    state.spotify.shuffle = Boolean(player.shuffle_state);
    state.spotify.repeat = player.repeat_state || "off";
    if (player.device && typeof player.device.volume_percent === "number") {
      state.spotify.volume = player.device.volume_percent;
    }
    if (statusEl) {
      statusEl.textContent = user ? `Spotify: connected (${user})` : "Spotify: connected";
    }
    if (trackEl) {
      trackEl.textContent = track || "No active playback.";
    }
    const volumeEl = $("spotify-volume");
    if (volumeEl && typeof state.spotify.volume === "number") {
      volumeEl.value = String(state.spotify.volume);
    }
    const shuffleEl = $("spotify-shuffle");
    if (shuffleEl) {
      shuffleEl.checked = Boolean(state.spotify.shuffle);
    }
    const repeatEl = $("spotify-repeat");
    if (repeatEl) {
      repeatEl.value = state.spotify.repeat;
    }
    setSpotifyControlsEnabled(true);
    if (Date.now() - state.spotifyDevicesAt > 15000) {
      refreshSpotifyDevices();
    }
  } catch (error) {
    if (statusEl) {
      statusEl.textContent = "Spotify: unavailable";
    }
    setSpotifyControlsEnabled(false);
    reportIssue("PHX-SPT-101", "spotify_status_unavailable", error?.message || String(error), {}, "warn", true);
  }
}

async function connectSpotify() {
  try {
    const data = await api.spotifyAuth();
    const url = data && data.url;
    if (url) {
      const win = window.open(url, "_blank");
      if (!win) {
        toast("Popup blocked. Open Spotify auth link in your browser.", "warn");
      } else {
        toast("Spotify auth opened.", "info");
      }
    } else {
      toast("Spotify auth unavailable.", "warn");
    }
  } catch (error) {
    toast("Spotify auth failed.", "warn");
  }
}

async function disconnectSpotify() {
  try {
    await api.spotifyDisconnect();
    state.spotify.authorized = false;
    setSpotifyControlsEnabled(false);
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify disconnect failed.", "warn");
  }
}

async function spotifyPlayResume() {
  try {
    await api.spotifyPlay({});
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify play failed.", "warn");
    reportIssue("PHX-SPT-201", "spotify_play_failed", error?.message || String(error), {}, "warn", true);
  }
}

async function spotifyPlayFromUrl() {
  const context = state.audioSettings.spotifyUrl || "";
  if (!context) {
    toast("Paste a Spotify link first.", "warn");
    return;
  }
  try {
    await api.spotifyPlay({ context });
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify play failed.", "warn");
    reportIssue("PHX-SPT-201", "spotify_play_failed", error?.message || String(error), {}, "warn", true);
  }
}

async function spotifyPause() {
  try {
    await api.spotifyPause();
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify pause failed.", "warn");
    reportIssue("PHX-SPT-202", "spotify_pause_failed", error?.message || String(error), {}, "warn", true);
  }
}

async function spotifyNext() {
  try {
    await api.spotifyNext();
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify next failed.", "warn");
    reportIssue("PHX-SPT-203", "spotify_next_failed", error?.message || String(error), {}, "warn", true);
  }
}

async function spotifyPrevious() {
  try {
    await api.spotifyPrevious();
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify previous failed.", "warn");
    reportIssue("PHX-SPT-204", "spotify_previous_failed", error?.message || String(error), {}, "warn", true);
  }
}

async function spotifyTransferDevice() {
  const select = $("spotify-device");
  if (!select || !select.value) {
    toast("Select a Spotify device.", "warn");
    return;
  }
  try {
    await api.spotifyTransfer({ device_id: select.value, play: true });
    refreshSpotifyStatus();
  } catch (error) {
    toast("Spotify transfer failed.", "warn");
    reportIssue("PHX-SPT-205", "spotify_transfer_failed", error?.message || String(error), {}, "warn", true);
  }
}

function renderAudioProfiles(profiles, active) {
  const select = $("audio-profile-select");
  if (!select) {
    return;
  }
  select.innerHTML = "";
  (profiles || []).forEach((profile) => {
    const name = profile && profile.name ? String(profile.name) : "";
    if (!name) {
      return;
    }
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
  if (active && select.querySelector(`option[value="${active}"]`)) {
    select.value = active;
  }
}

async function refreshAudioProfiles() {
  try {
    const data = await api.audioProfiles();
    const profiles = Array.isArray(data.profiles) ? data.profiles : [];
    state.audioProfiles = profiles;
    state.audioProfileActive = data.active || "";
    renderAudioProfiles(profiles, state.audioProfileActive);
  } catch (error) {
    const select = $("audio-profile-select");
    if (select) {
      select.innerHTML = "";
    }
    reportIssue("PHX-AUD-112", "audio_profiles_unavailable", error?.message || String(error), {}, "warn", true);
  }
}

async function applyAudioProfile() {
  const select = $("audio-profile-select");
  if (!select || !select.value) {
    toast("Select a profile first.", "warn");
    return;
  }
  try {
    const data = await api.audioProfileApply({ name: select.value });
    if (data && data.eq) {
      const bands = state.audioEq.bands || [];
      state.audioEq.input = normalizeEqValues(data.eq.input, bands);
      state.audioEq.output = normalizeEqValues(data.eq.output, bands);
      renderAudioEqList();
    }
    state.audioProfileActive = select.value;
    toast("Profile applied.");
  } catch (error) {
    toast("Profile apply failed.", "warn");
  }
}

async function saveAudioProfile() {
  const input = $("audio-profile-name");
  const name = input ? input.value.trim() : "";
  if (!name) {
    toast("Enter a profile name.", "warn");
    return;
  }
  try {
    await api.audioProfileSave({
      name,
      eq: {
        input: state.audioEq.input,
        output: state.audioEq.output,
      },
    });
    if (input) {
      input.value = "";
    }
    toast("Profile saved.");
    refreshAudioProfiles();
  } catch (error) {
    toast("Profile save failed.", "warn");
  }
}

function setExamPrompt(message) {
  safeText("audio-exam-prompt", message || "");
}

function normalizeSpeechText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function speechSimilarity(expected, received) {
  const a = normalizeSpeechText(expected);
  const b = normalizeSpeechText(received);
  if (!a || !b) {
    return 0;
  }
  if (a === b) {
    return 1;
  }
  const dp = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));
  for (let i = 0; i <= a.length; i += 1) dp[i][0] = i;
  for (let j = 0; j <= b.length; j += 1) dp[0][j] = j;
  for (let i = 1; i <= a.length; i += 1) {
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + cost
      );
    }
  }
  const distance = dp[a.length][b.length];
  return 1 - distance / Math.max(a.length, b.length, 1);
}

function updateHearingStatus(message) {
  const status = $("audio-hearing-status");
  if (!status) {
    return;
  }
  if (message) {
    status.textContent = message;
    return;
  }
  if (!state.audioHearingTest.active) {
    status.textContent = "Idle.";
    return;
  }
  const total = state.audioHearingTest.frequencies.length || 0;
  const step = Math.min(state.audioHearingTest.index + 1, total);
  const freq = state.audioHearingTest.frequencies[state.audioHearingTest.index];
  const label = freq ? `${formatEqBandLabel(freq)} Hz` : "--";
  status.textContent = `Step ${step}/${total}: ${label}`;
  setExamPrompt(`Do you hear ${label}? (Yes/No)`);
}

function updateSpeechStatus(message) {
  const status = $("audio-speech-status");
  if (!status) {
    return;
  }
  if (message) {
    status.textContent = message;
    return;
  }
  if (!state.audioSpeechTest.active) {
    status.textContent = "Idle.";
    return;
  }
  const total = state.audioSpeechTest.phrases.length || 0;
  const step = Math.min(state.audioSpeechTest.index + 1, total);
  status.textContent = `Phrase ${step}/${total}: Listen and reply.`;
  setExamPrompt("Repeat or type what you heard.");
}

function markAudioExamCompleted() {
  state.audioExamStatus.completedAt = Date.now();
  state.audioExamStatus.runCount = (state.audioExamStatus.runCount || 0) + 1;
  saveAudioExamStatus(state.activeUserId);
}

function startAudioExam() {
  stopHearingTest();
  stopSpeechTest();
  state.audioExam = { active: true, stage: "tone", startedAt: Date.now() };
  updateAudioProfileStatus("Audio exam started.");
  syncAudioProfileLab();
  startHearingTest();
}

function stopAudioExam() {
  state.audioExam = { active: false, stage: "", startedAt: 0 };
  stopHearingTest();
  stopSpeechTest();
  setExamPrompt("Exam stopped.");
  updateAudioProfileStatus("Audio exam stopped.");
  syncAudioProfileLab();
}

function startHearingTest() {
  const targetSelect = $("audio-hearing-target");
  const target = targetSelect ? targetSelect.value : "output";
  const bands =
    state.audioEq.bands && state.audioEq.bands.length
      ? state.audioEq.bands.slice()
      : AUDIO_HEARING_DEFAULT_BANDS.slice();
  state.audioHearingTest = {
    active: true,
    index: 0,
    target,
    frequencies: bands,
    results: [],
  };
  updateAudioProfileStatus(`Hearing test started (${target}).`);
  updateHearingStatus();
  playHearingTone();
}

function stopHearingTest() {
  state.audioHearingTest.active = false;
  updateHearingStatus("Hearing test stopped.");
  setExamPrompt("Hearing test stopped.");
  updateAudioProfileStatus("Hearing test stopped.");
  api.audioStop().catch(() => {});
}

function playHearingTone() {
  if (!state.audioHearingTest.active) {
    return;
  }
  const freq = state.audioHearingTest.frequencies[state.audioHearingTest.index];
  if (!freq) {
    return;
  }
  const outputSelect = $("audio-output");
  const output = outputSelect && outputSelect.value ? Number(outputSelect.value) : null;
  api
    .audioTone({
      kind: "sine",
      frequency: Number(freq),
      duration: 1.2,
      amplitude: 0.25,
      device: output,
    })
    .catch(() => {});
  updateHearingStatus();
}

async function recordHearingResponse(response) {
  if (!state.audioHearingTest.active) {
    return;
  }
  const freq = state.audioHearingTest.frequencies[state.audioHearingTest.index];
  if (!freq) {
    return;
  }
  const userId = state.activeUserId || "default";
  try {
    await api.audioHearingTestAdd({
      user: userId,
      target: state.audioHearingTest.target,
      frequency: Number(freq),
      response,
      test_type: "tone",
    });
  } catch (error) {
    toast("Hearing response failed.", "warn");
  }
  state.audioHearingTest.results.push({ frequency: Number(freq), response });
  state.audioHearingTest.index += 1;
  if (state.audioHearingTest.index >= state.audioHearingTest.frequencies.length) {
    finishHearingTest();
  } else {
    playHearingTone();
  }
}

async function finishHearingTest() {
  state.audioHearingTest.active = false;
  updateHearingStatus("Hearing test complete.");
  setExamPrompt("Hearing test complete.");
  await refreshHearingSummary(state.audioHearingTest.target);
  if (state.audioExam.active && state.audioExam.stage === "tone") {
    state.audioExam.stage = "speech";
    startSpeechTest();
  }
}

async function refreshHearingSummary(target) {
  const userId = state.activeUserId || "default";
  try {
    const data = await api.audioHearingSummary({ user: userId, target });
    const suggested = Array.isArray(data.suggested_eq) ? data.suggested_eq : [];
    state.audioSuggestedEqBase[target] = suggested;
    updateSuggestedEqForTarget(target);
    updateAudioProfileStatus(`Hearing test complete. Suggested ${target} EQ ready.`);
  } catch (error) {
    updateAudioProfileStatus("Hearing summary unavailable.");
  }
}

function startSpeechTest() {
  const phrases = shuffleList(SPEECH_TEST_PHRASES).slice(0, 6);
  state.audioSpeechTest = {
    active: true,
    index: 0,
    phrases,
    expected: phrases[0] || "",
    similarity: 0,
  };
  updateSpeechStatus();
  setExamPrompt("Listen and repeat or type what you hear.");
  playSpeechPhrase();
}

function stopSpeechTest() {
  if (!state.audioSpeechTest.active) {
    return;
  }
  state.audioSpeechTest.active = false;
  updateSpeechStatus("Speech test stopped.");
  setExamPrompt("Speech test stopped.");
}

function playSpeechPhrase() {
  if (!state.audioSpeechTest.active) {
    toast("Start the speech test first.", "warn");
    return;
  }
  const expected = state.audioSpeechTest.expected;
  if (!expected) {
    return;
  }
  const payload = {
    text: expected,
    voice: state.audioSettings.voice,
    rate: state.audioSettings.rate,
    pitch: state.audioSettings.pitch,
  };
  updateSpeechStatus("Playing phrase...");
  api
    .tts(payload)
    .then((audioData) => {
      const blob = new Blob([audioData], { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.volume = 0.9;
      audio.addEventListener(
        "ended",
        () => {
          URL.revokeObjectURL(url);
          updateSpeechStatus();
        },
        { once: true }
      );
      audio.play().catch(() => {});
    })
    .catch(() => {
      updateSpeechStatus("Speech playback failed.");
      toast("Speech test playback failed.", "warn");
    });
}

async function submitSpeechResponse(inputValue) {
  if (!state.audioSpeechTest.active) {
    toast("Start the speech test first.", "warn");
    return;
  }
  const expected = state.audioSpeechTest.expected;
  if (!expected) {
    return;
  }
  const received = String(inputValue || "").trim();
  const similarity = speechSimilarity(expected, received);
  const correct = similarity >= 0.75;
  const userId = state.activeUserId || "default";
  try {
    await api.audioHearingTestAdd({
      user: userId,
      target: "output",
      response: correct ? "speech_correct" : "speech_incorrect",
      test_type: "speech",
      expected,
      received,
      correct,
      similarity,
    });
  } catch (error) {
    toast("Speech response failed.", "warn");
  }
  state.audioSpeechTest.similarity = similarity;
  advanceSpeechTest(correct);
}

async function recordSpeechRepeat() {
  if (!state.audioSpeechTest.active) {
    toast("Start the speech test first.", "warn");
    return;
  }
  const expected = state.audioSpeechTest.expected;
  updateSpeechStatus("Recording your repeat...");
  try {
    const data = await api.audioVoiceRepeat({
      expected,
      duration: 3,
    });
    const transcript = data && data.transcript ? data.transcript : "";
    const similarity = typeof data.similarity === "number" ? data.similarity : 0;
    const correct = Boolean(data.match);
    const metrics = data && data.metrics ? data.metrics : {};
    state.audioVoiceMetrics = {
      rms: typeof metrics.rms === "number" ? metrics.rms : state.audioVoiceMetrics.rms,
      peak: typeof metrics.peak === "number" ? metrics.peak : state.audioVoiceMetrics.peak,
    };
    const userId = state.activeUserId || "default";
    await api.audioHearingTestAdd({
      user: userId,
      target: "output",
      response: correct ? "repeat_correct" : "repeat_incorrect",
      test_type: "speech",
      expected,
      received: transcript,
      correct,
      similarity,
    });
    if (Array.isArray(data.suggested_eq)) {
      state.audioSuggestedEqBase.input = data.suggested_eq;
      updateSuggestedEqForTarget("input");
    }
    syncAudioProfileLab();
    updateSpeechStatus(correct ? "Repeat matched." : "Repeat mismatch.");
    advanceSpeechTest(correct);
  } catch (error) {
    updateSpeechStatus("Repeat capture failed.");
    toast("Repeat capture failed.", "warn");
  }
}

function advanceSpeechTest(correct) {
  const input = $("audio-speech-input");
  if (input) {
    input.value = "";
  }
  state.audioSpeechTest.index += 1;
  if (state.audioSpeechTest.index >= state.audioSpeechTest.phrases.length) {
    finishSpeechTest();
    return;
  }
  state.audioSpeechTest.expected = state.audioSpeechTest.phrases[state.audioSpeechTest.index];
  updateSpeechStatus(correct ? "Correct. Next phrase..." : "Noted. Next phrase...");
  playSpeechPhrase();
}

async function finishSpeechTest() {
  state.audioSpeechTest.active = false;
  updateSpeechStatus("Speech test complete.");
  setExamPrompt("Speech test complete.");
  await refreshHearingSummary("output");
  if (state.audioExam.active) {
    state.audioExam = { active: false, stage: "", startedAt: 0 };
    markAudioExamCompleted();
    updateAudioProfileStatus("Audio exam complete. Run voice calibration for input EQ.");
    syncAudioProfileLab();
  }
}

async function runVoiceCalibration() {
  const durationInput = $("audio-voice-duration");
  const duration = clampNumber(
    durationInput ? durationInput.value : 3,
    0.5,
    8,
    3
  );
  updateAudioProfileStatus("Recording voice sample...");
  try {
    const data = await api.audioVoiceCalibrate({ duration });
    const metrics = data && data.metrics ? data.metrics : {};
    state.audioVoiceMetrics = {
      rms: typeof metrics.rms === "number" ? metrics.rms : null,
      peak: typeof metrics.peak === "number" ? metrics.peak : null,
    };
    const suggested = Array.isArray(data.suggested_eq) ? data.suggested_eq : [];
    state.audioSuggestedEqBase.input = suggested;
    updateSuggestedEqForTarget("input");
    syncAudioProfileLab();
    updateAudioProfileStatus("Voice calibration complete. Suggested input EQ ready.");
  } catch (error) {
    updateAudioProfileStatus("Voice calibration failed.");
    toast("Voice calibration failed.", "warn");
  }
}

function applySuggestedEq(target) {
  const suggested = state.audioSuggestedEq[target] || [];
  if (!Array.isArray(suggested) || suggested.length === 0) {
    toast("No suggested EQ available yet.", "warn");
    return;
  }
  const bands =
    state.audioEq.bands && state.audioEq.bands.length
      ? state.audioEq.bands
      : AUDIO_HEARING_DEFAULT_BANDS;
  state.audioEq[target] = normalizeEqValues(suggested, bands);
  state.audioEqTarget = target;
  renderAudioEqList();
  api.audioEqSet({ target, bands: state.audioEq[target] }).catch(() => {});
  if (target === "output") {
    api
      .audioEqApply({ target, bands: state.audioEq[target] })
      .then(() => refreshAudioEqEngine())
      .catch(() => {});
  }
  toast(`Suggested ${target} EQ applied.`);
}

async function saveAudioProfileLab() {
  const user = getActiveUser();
  const prefs = normalizeAudioProfilePrefs(state.audioProfilePrefs);
  const name = `${user?.settings?.loginUser || "User"} Auto`;
  const bands =
    state.audioEq.bands && state.audioEq.bands.length
      ? state.audioEq.bands
      : AUDIO_HEARING_DEFAULT_BANDS;
  const inputEq = state.audioSuggestedEq.input.length
    ? normalizeEqValues(state.audioSuggestedEq.input, bands)
    : state.audioEq.input;
  const outputEq = state.audioSuggestedEq.output.length
    ? normalizeEqValues(state.audioSuggestedEq.output, bands)
    : state.audioEq.output;
  const notes = `Auto profile. Warmth ${prefs.warmth}, Clarity ${prefs.clarity}, Air ${prefs.air}, Bass ${prefs.bass}.`;
  try {
    await api.audioProfileSave({
      name,
      eq: { input: inputEq, output: outputEq },
      notes,
    });
    toast("Auto profile saved.");
    refreshAudioProfiles();
  } catch (error) {
    toast("Auto profile save failed.", "warn");
  }
}

function renderAudioSessions(sessions) {
  const list = $("audio-session-list");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  if (!Array.isArray(sessions) || sessions.length === 0) {
    list.textContent = "No active sessions.";
    return;
  }
  sessions.forEach((session) => {
    const row = document.createElement("div");
    row.className = "audio-session";
    const top = document.createElement("div");
    top.className = "audio-session-top";
    const title = document.createElement("span");
    title.textContent = session.name || "Session";
    const mute = document.createElement("input");
    mute.type = "checkbox";
    mute.checked = Boolean(session.mute);
    top.appendChild(title);
    top.appendChild(mute);
    const controls = document.createElement("div");
    controls.className = "audio-session-controls";
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "100";
    slider.value = String(Math.round((session.volume || 0) * 100));
    const valueEl = document.createElement("span");
    valueEl.className = "audio-eq-value";
    valueEl.textContent = `${slider.value}%`;
    slider.addEventListener("input", () => {
      valueEl.textContent = `${slider.value}%`;
    });
    slider.addEventListener("change", () => {
      api
        .audioSystemSessionSet({
          session_id: session.id,
          volume: Number(slider.value) / 100,
        })
        .catch(() => {});
    });
    mute.addEventListener("change", () => {
      api
        .audioSystemSessionSet({
          session_id: session.id,
          mute: mute.checked,
        })
        .catch(() => {});
    });
    controls.appendChild(slider);
    controls.appendChild(valueEl);
    row.appendChild(top);
    row.appendChild(controls);
    list.appendChild(row);
  });
}

function syncMasterUI() {
  const vol = $("audio-master-volume");
  const label = $("audio-master-value");
  const mute = $("audio-master-mute");
  const disabled = !state.audioMaster.available;
  if (vol) {
    vol.value = String(state.audioMaster.volume);
    vol.disabled = disabled;
  }
  if (label) {
    label.textContent = `${state.audioMaster.volume}%`;
  }
  if (mute) {
    mute.checked = Boolean(state.audioMaster.mute);
    mute.disabled = disabled;
  }
}

async function refreshAudioSystemMix() {
  try {
    const master = await api.audioSystemMaster("output");
    if (master && master.available) {
      state.audioMaster = {
        volume: Math.round((master.volume || 0) * 100),
        mute: Boolean(master.mute),
        available: true,
      };
    } else {
      state.audioMaster.available = false;
    }
    syncMasterUI();
  } catch (error) {
    state.audioMaster.available = false;
    syncMasterUI();
  }
  try {
    const data = await api.audioSystemSessions();
    if (data && data.available) {
      state.audioSessions = data.sessions || [];
    } else {
      state.audioSessions = [];
    }
  } catch (error) {
    state.audioSessions = [];
  }
  renderAudioSessions(state.audioSessions);
}

async function playAudioTone(kind) {
  const outputSelect = $("audio-output");
  const output = outputSelect?.value ? Number(outputSelect.value) : undefined;
  try {
    if (kind === "sweep") {
      await api.audioTone({
        kind: "sweep",
        start_frequency: 31,
        end_frequency: 16000,
        duration: 6,
        amplitude: 0.15,
        device: output,
      });
    } else {
      await api.audioTone({
        kind: "sine",
        frequency: 440,
        duration: 2,
        amplitude: 0.2,
        device: output,
      });
    }
    toast("Tone playing.");
  } catch (error) {
    toast("Tone failed.", "warn");
  }
}

async function stopAudioTone() {
  try {
    await api.audioStop();
    toast("Tone stopped.");
  } catch (error) {
    toast("Stop failed.", "warn");
  }
}

async function pollAudioMetrics() {
  if (!state.settings.showAudio) {
    return;
  }
  if (state.activeModule !== "audio" && state.activeModule !== "all") {
    return;
  }
  const rmsEl = $("audio-rms");
  const peakEl = $("audio-peak");
  if (!rmsEl || !peakEl) {
    return;
  }
  try {
    const data = await api.audioSpectrum();
    rmsEl.textContent = data.rms ? data.rms.toFixed(3) : "--";
    peakEl.textContent = data.peak ? data.peak.toFixed(3) : "--";
  } catch (error) {
    rmsEl.textContent = "--";
    peakEl.textContent = "--";
  }
}

async function sendChat() {
  if (!requireUnlocked()) {
    return;
  }
  if (state.chatBusy) {
    return;
  }
  const input = $("chat-input");
  const text = input ? input.value.trim() : "";
  if (state.pendingImageLoading) {
    state.queuedMessage = text;
    if (input) {
      input.value = "";
    }
    toast("Image loading. Will send when ready.", "info");
    return;
  }
  const hasImage = !!state.pendingImage;
  if (!text && !hasImage) {
    return;
  }
  // Contextual visualization intent: "think of an apple for 5 seconds", "focus on a circle for 3 heartbeats"
  const visIntent =
    text.match(/(?:think|focus|visualize|imagine)[^\\w]+(?:of|about)?\\s+(.+?)\\s+for\\s+(\\d+)\\s*(seconds?|secs?|heartbeats?)/i) ||
    text.match(/hold\\s+(.+?)\\s+for\\s+(\\d+)\\s*(seconds?|secs?|heartbeats?)/i);
  if (visIntent) {
    const thought = (visIntent[1] || "an idea").trim();
    const rawDur = Number(visIntent[2] || 5);
    const units = (visIntent[3] || "").toLowerCase();
    const duration = Math.max(1, rawDur) * (units.includes("heartbeat") ? 1 : 1); // 1 heartbeat ~1s
    queueVisualization(thought, duration);
    addChat("user", text);
    addChat("assistant", `I'll hold the shape of "${thought}" for ${duration} seconds and then report back.`);
    if (input) input.value = "";
    return;
  }
  // Stop/cancel current visualization
  if (/\\b(stop|cancel)\\b/i.test(text) && state.visualization) {
    state.visualization = null;
    state.orbOverride = null;
    state.orbOverrideUntil = 0;
    addChat("assistant", "Visualization cancelled.");
    if (input) input.value = "";
    return;
  }
  // Reinforcement (positive/negative feedback)
  if (state.lastVisualizationThought) {
    if (/\\b(good job|i saw|that worked|nice|well done)\\b/i.test(text)) {
      state.vizReinforce = Math.min(5, state.vizReinforce + 1);
      addChat("assistant", "Noted. I'll try visualizing more vividly next time.");
      if (input) input.value = "";
      return;
    }
    if (/\\b(no|don\\'t|didn\\'t work|stop)\\b/i.test(text)) {
      state.vizReinforce = Math.max(0, state.vizReinforce - 1);
      addChat("assistant", "Understood. I'll ease off that visualization.");
      if (input) input.value = "";
      return;
    }
  }
  // Quick visualize command: "/visualize 5 apple" or "/visualize apple"
  if (text.startsWith("/visualize")) {
    const parts = text.split(" ").filter(Boolean);
    let duration = 5;
    let thought = parts.slice(1).join(" ").trim();
    if (parts.length > 2 && !Number.isNaN(Number(parts[1]))) {
      duration = Math.max(1, Number(parts[1]));
      thought = parts.slice(2).join(" ").trim();
    }
    if (!thought) thought = "an idea";
    queueVisualization(thought, duration);
    addChat("user", text);
    addChat("assistant", `Thinking about "${thought}" for ${duration} seconds...`);
    if (input) input.value = "";
    return;
  }
  if (input) {
    input.value = "";
    input.disabled = true;
  }
  const sendBtn = $("chat-send");
  if (sendBtn) {
    sendBtn.disabled = true;
  }
  state.chatBusy = true;
  const historyLine = text || (hasImage ? "[image]" : "");
  if (text) {
    addChat("user", text);
  }
  if (hasImage && state.pendingImage?.dataUrl) {
    addChatImage("user", state.pendingImage.dataUrl);
  }
  if (historyLine) {
    pushHistory("user", historyLine);
    state.lastUserAt = Date.now();
  }
  const thoughtSeed = text || (hasImage ? "image" : "");
  state.orbThought = thoughtSeed.slice(0, 80);
  safeText("orb-thoughts", `Thought stream: ${state.orbThought}`);
  setOrbState("thinking", "processing");
  try {
    let visionNote = "";
    let imagePayload = null;
    if (state.pendingImage) {
      const pending = state.pendingImage;
      state.orbImageDataUrl = pending.dataUrl;
      state.orbImageKey = `${pending.name}:${pending.dataUrl.length}:${Date.now()}`;
      state.orbOverride = { mode: "image" };
      state.orbOverrideUntil = performance.now() + 14000;
      imagePayload = {
        image_b64: pending.dataUrl,
        image_filename: pending.name,
        image_prompt: text || "Describe the image briefly.",
      };
      try {
        const vision = await api.visionAnalyze({
          image_b64: pending.dataUrl,
          filename: pending.name,
          prompt: text || "Describe the image briefly.",
        });
        visionNote = (vision && vision.summary) || "";
        if (visionNote) {
          const memoryLine = `Visual memory: ${visionNote}`;
          pushHistory("system", memoryLine);
        }
        if (vision && vision.meta && vision.meta.vision_mode === "metadata_fallback") {
          toast("Vision fallback: metadata only. Check Ollama vision model.", "warn");
        }
      } catch (error) {
        const msg = (error && error.message) || "";
        if (msg.includes("vision_model_missing")) {
          addChat(
            "assistant",
            "Vision model not configured. Set OLLAMA_VISION_MODEL to a vision-capable Ollama model."
          );
          toast("Vision model missing.", "alert");
        } else {
          addChat("assistant", "Visual memory capture failed.");
          toast("Image analysis failed.", "alert");
        }
      }
    }
    const response = await api.aiLocal({
      message: text || "Analyze the attached image.",
      history: state.history,
      vision: visionNote,
      ...(imagePayload || {}),
    });
    if (state.pendingImage) {
      clearPendingImage();
    }
    const rawReply = response.reply || "...";
    const parsed = parseOrbDirectives(rawReply);
    const reply = parsed.cleaned || rawReply;
    addChat("assistant", reply);
    pushHistory("assistant", reply);
    const orbText = reply.trim();
    state.orbThought = orbText.slice(0, 80);
    if (orbText) {
      state.orbOverride = { mode: "glyphs", text: orbText };
      state.orbOverrideUntil = performance.now() + 12000;
    }
    safeText("orb-thoughts", `Thought stream: ${state.orbThought}`);
    if (parsed.action) {
      state.orbAction = parsed.action;
      state.orbActionUntil = performance.now() + 5200;
    }
      if (parsed.override) {
        if (parsed.override.mode === "clear") {
          state.orbOverride = null;
          state.orbOverrideUntil = 0;
        } else {
          state.orbOverride = parsed.override;
          state.orbOverrideUntil = performance.now() + 7200;
        }
      }
      updateConsciousnessFromReply({ reply, userText: text });
      if (state.audioSettings.voiceFeedback) {
        await speakText(reply);
      } else if (state.audioSettings.replyChime) {
        playSound("chime", state.audioSettings.chimeVolume / 100);
      }
    setOrbState("listening", "idle");
  } catch (error) {
    const msg = error?.message || String(error);
    reportIssue("PHX-CHAT-001", "chat_failed", msg, { apiBase: api.baseUrl || "" }, "warn", true);
    if (/failed to fetch|network|timeout|offline/i.test(msg)) {
      addChat("assistant", "System offline. Check backend.");
    } else {
      addChat("assistant", `Chat failed: ${msg}`);
    }
    toast("Chat failed.", "alert");
    setOrbState("listening", "idle");
  } finally {
    if (hasImage) {
      clearPendingImage();
    }
    state.chatBusy = false;
    if (input) {
      input.disabled = false;
      input.focus();
    }
    if (sendBtn) {
      sendBtn.disabled = false;
    }
  }
}

async function speakText(text) {
  if (!state.audioSettings.voiceFeedback) {
    return;
  }
  const sanitized = sanitizeForTts(text);
  try {
    const payload = {
      text: sanitized,
      voice: state.audioSettings.voice,
      rate: state.audioSettings.rate,
      pitch: state.audioSettings.pitch,
    };
    const audioData = await api.tts(payload);
    const blob = new Blob([audioData], { type: "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    safeText("orb-audio", "Voice: active");
    setOrbState("speaking", "voicing");
    await audio.play();
    await new Promise((resolve) => {
      audio.addEventListener("ended", resolve, { once: true });
    });
    URL.revokeObjectURL(url);
    safeText("orb-audio", "Voice: enabled");
  } catch (error) {
    safeText("orb-audio", "Voice: error");
    toast("Voice playback failed.", "warn");
  }
}

function sanitizeForTts(text) {
  if (!text) return "";
  let cleaned = String(text);
  cleaned = cleaned.replace(/\[\[ACTION\]\][\s\S]*?\[\[\/ACTION\]\]/gi, " ");
  cleaned = cleaned.replace(/\[\[\/?ACTION\]\]/gi, " ");
  cleaned = cleaned.replace(/```[\s\S]*?```/g, " ");
  cleaned = cleaned.replace(/`[^`]+`/g, " ");
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  cleaned = cleaned.replace(/<[^>]+>/g, " ");
  cleaned = cleaned.replace(/https?:\/\/\S+|www\.\S+/gi, " ");
  cleaned = cleaned.replace(/\b[A-Za-z]:\\[^\s]+/g, " ");
  cleaned = cleaned.replace(/^\s*(assistant|system|user|bjorgsun-26)\s*[:\\-].*$/gim, " ");
  cleaned = cleaned.replace(/^\s*\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?\s*$/gim, " ");
  cleaned = cleaned.replace(/^\s*(?:[-*+]|\d+[.)])\s+/gim, "");
  cleaned = cleaned.replace(/^\s*(?:#{1,6}|>+)\s*/gim, "");
  cleaned = cleaned.replace(/^[^A-Za-z0-9]+/, " ");
  cleaned = cleaned.replace(/[{}<>]/g, " ");
  cleaned = cleaned.replace(/[\x00-\x1f\x7f]/g, " ");
  cleaned = cleaned.replace(/[^\x20-\x7E]/g, " ");
  cleaned = cleaned.replace(/\s+/g, " ").trim();
  return cleaned;
}

let usbDriveCache = [];

function setUsbStatus(message) {
  safeText("usb-status", message || "");
}

function setUsbSyncStatus(message) {
  safeText("usb-sync-status", message || "");
}

function setRemoteStatus(message) {
  safeText("remote-status", message || "");
}

function setRemoteLinks(links) {
  const el = $("remote-links");
  if (!el) {
    return;
  }
  if (!Array.isArray(links) || links.length === 0) {
    el.textContent = "";
    return;
  }
  el.innerHTML = "";
  links.forEach((link) => {
    const item = document.createElement("div");
    item.className = "link-item";
    const a = document.createElement("a");
    a.href = link;
    a.textContent = link;
    a.target = "_blank";
    a.rel = "noreferrer";
    item.appendChild(a);
    el.appendChild(item);
  });
}

function setRemoteTunnelStatus(message) {
  safeText("remote-tunnel-status", message || "");
}

function setRemoteTunnelLink(link) {
  const el = $("remote-tunnel-link");
  if (!el) {
    return;
  }
  if (!link) {
    el.textContent = "";
    return;
  }
  el.innerHTML = "";
  const a = document.createElement("a");
  a.href = link;
  a.textContent = link;
  a.target = "_blank";
  a.rel = "noreferrer";
  el.appendChild(a);
}

function getSelectedUsbDrive() {
  const select = $("usb-drive-select");
  if (!select) {
    return "";
  }
  return (select.value || "").trim();
}

function getUsbLocalPath() {
  const input = $("setting-usb-local-path");
  return (input && input.value ? input.value : "").trim();
}

function detectUsbPresetFromSettings(settings = state.settings) {
  const config = {
    usbIncludeApp: Boolean(settings.usbIncludeApp),
    usbIncludeMemory: Boolean(settings.usbIncludeMemory),
    usbIncludeUserData: Boolean(settings.usbIncludeUserData),
  };
  const match = Object.entries(USB_COPY_PRESETS).find(([, preset]) =>
    Object.keys(config).every((key) => preset[key] === config[key])
  );
  return match ? match[0] : "custom";
}

function syncUsbPresetUI() {
  const select = $("usb-copy-preset");
  if (!select) {
    return;
  }
  const preset = detectUsbPresetFromSettings();
  state.settings.usbCopyPreset = preset;
  select.value = preset;
}

function syncUsbIncludeCheckboxes() {
  const mapping = [
    ["usb-include-os", "usbIncludeOs"],
    ["usb-include-app", "usbIncludeApp"],
    ["usb-include-memory", "usbIncludeMemory"],
    ["usb-include-user", "usbIncludeUserData"],
  ];
  mapping.forEach(([id, key]) => {
    const el = $(id);
    if (el) {
      el.checked = Boolean(state.settings[key]);
    }
  });
}

function applyUsbPreset(preset, { persist = true } = {}) {
  if (!preset) {
    return;
  }
  if (preset === "custom") {
    state.settings.usbCopyPreset = "custom";
    if (persist) {
      saveSettings();
    }
    syncUsbIncludeCheckboxes();
    syncUsbPresetUI();
    return;
  }
  const config = USB_COPY_PRESETS[preset];
  if (!config) {
    return;
  }
  state.settings.usbCopyPreset = preset;
  state.settings.usbIncludeApp = config.usbIncludeApp;
  state.settings.usbIncludeMemory = config.usbIncludeMemory;
  state.settings.usbIncludeUserData = config.usbIncludeUserData;
  if (persist) {
    saveSettings();
  }
  syncUsbIncludeCheckboxes();
  syncUsbPresetUI();
}

function updateUsbPresetFromSelection() {
  state.settings.usbCopyPreset = detectUsbPresetFromSettings();
  syncUsbPresetUI();
}

function getRemoteHost() {
  const input = $("setting-remote-host");
  return (input && input.value ? input.value : "").trim();
}

function setDisplayStatus(message) {
  safeText("display-status", message || "");
}

function defaultMonitorSelection(monitors) {
  const landscape = (monitors || []).filter((monitor) => {
    const width = Number(monitor.width || 0);
    const height = Number(monitor.height || 0);
    return width >= height;
  });
  const base = landscape.length ? landscape : monitors || [];
  return base.map((monitor, index) => monitor.id || `display-${index + 1}`);
}

function renderDisplayMonitors(monitors) {
  const list = $("display-list");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  if (!Array.isArray(monitors) || !monitors.length) {
    setDisplayStatus("No monitors detected.");
    return;
  }
  let selected = Array.isArray(state.settings.desktopViewMonitors)
    ? state.settings.desktopViewMonitors
    : [];
  if (!selected.length) {
    selected = defaultMonitorSelection(monitors);
    state.settings.desktopViewMonitors = selected;
    saveSettings();
  }
  const selectedSet = new Set(selected);
  monitors.forEach((monitor, index) => {
    const id = monitor.id || `display-${index + 1}`;
    const label = monitor.label || `Display ${index + 1}`;
    const primary = monitor.primary ? "Primary" : "Secondary";
    const resolution = monitor.width && monitor.height ? `${monitor.width}x${monitor.height}` : "Unknown";
    const origin =
      monitor.x !== undefined && monitor.y !== undefined ? `${monitor.x}, ${monitor.y}` : "0, 0";
    const orientation = monitor.orientation || "";
    const card = document.createElement("label");
    card.className = "monitor-card";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.monitorId = id;
    checkbox.checked = selectedSet.has(id);
    const meta = document.createElement("div");
    meta.className = "monitor-meta";
    const title = document.createElement("div");
    title.className = "monitor-title";
    title.textContent = `${label}${monitor.primary ? " - Main" : ""}`;
    const sub = document.createElement("div");
    sub.className = "monitor-sub";
    const orientationLabel = orientation ? ` - ${orientation}` : "";
    sub.textContent = `${primary} | ${resolution} | ${origin}${orientationLabel}`;
    meta.appendChild(title);
    meta.appendChild(sub);
    card.appendChild(checkbox);
    card.appendChild(meta);
    list.appendChild(card);
    checkbox.addEventListener("change", () => {
      const selectedIds = Array.from(list.querySelectorAll("input[type='checkbox']"))
        .filter((input) => input.checked)
        .map((input) => input.dataset.monitorId)
        .filter(Boolean);
      if (!selectedIds.length) {
        checkbox.checked = true;
        toast("Keep at least one monitor enabled.", "warn");
        return;
      }
      state.settings.desktopViewMonitors = selectedIds;
      saveSettings();
    });
  });
  setDisplayStatus(`Detected ${monitors.length} monitor(s).`);
}

async function refreshDisplayMonitors() {
  const list = $("display-list");
  if (!list) {
    return;
  }
  setDisplayStatus("Detecting displays...");
  list.innerHTML = "";
  try {
    const data = await api.systemMonitors();
    const monitors = Array.isArray(data?.monitors) ? data.monitors : [];
    state.displayMonitors = monitors;
    renderDisplayMonitors(monitors);
  } catch (err) {
    setDisplayStatus("Display scan failed.");
    logUiError("display_scan_failed", String(err || ""));
  }
}

async function refreshUsbDrives() {
  const select = $("usb-drive-select");
  if (!select) {
    return;
  }
  select.innerHTML = "";
  try {
    const data = await api.usbDrives();
    usbDriveCache = Array.isArray(data?.drives) ? data.drives : [];
    if (!usbDriveCache.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No removable drives found";
      select.appendChild(opt);
      setUsbStatus("No removable drives detected. Insert USB and refresh.");
      return;
    }
    usbDriveCache.forEach((drive) => {
      const root = drive.root || drive.drive || "";
      if (!root) {
        return;
      }
      const label = drive.label ? ` (${drive.label})` : "";
      const opt = document.createElement("option");
      opt.value = root;
      opt.textContent = `${root}${label}`;
      select.appendChild(opt);
    });
    setUsbStatus(`Found ${usbDriveCache.length} removable drive(s).`);
  } catch (err) {
    setUsbStatus("USB scan failed. Check connection and try again.");
    logUiError("usb_drive_scan_failed", String(err || ""));
  }
}

async function openUsbDrive() {
  const drive = getSelectedUsbDrive();
  if (!drive) {
    toast("Select a USB drive first.", "warn");
    return;
  }
  try {
    await api.usbOpen({ path: drive });
  } catch (err) {
    toast("Unable to open USB drive.", "error");
    logUiError("usb_open_failed", String(err || ""));
  }
}

async function openLocalUsbPath() {
  const path = getUsbLocalPath();
  if (!path) {
    toast("Set a local path first.", "warn");
    return;
  }
  try {
    await api.filesOpen({ path });
  } catch (err) {
    toast("Unable to open local path.", "error");
    logUiError("usb_local_open_failed", String(err || ""));
  }
}

async function copyProjectToUsb() {
  const drive = getSelectedUsbDrive();
  if (!drive) {
    toast("Select a USB drive first.", "warn");
    return;
  }
  if (!requireUnlocked()) {
    return;
  }
  setUsbStatus("Starting USB copy... check logs for progress.");
  try {
    const result = await api.usbCopy({
      drive,
      include_os: Boolean(state.settings.usbIncludeOs),
      include_app: Boolean(state.settings.usbIncludeApp),
      include_memory: Boolean(state.settings.usbIncludeMemory),
      include_user_data: Boolean(state.settings.usbIncludeUserData),
      preset: state.settings.usbCopyPreset || detectUsbPresetFromSettings(),
    });
    if (result?.log) {
      setUsbStatus(`Copy started. Log: ${result.log}`);
    } else {
      setUsbStatus("Copy started.");
    }
    toast("USB copy started.", "info");
  } catch (err) {
    setUsbStatus("USB copy failed. Check logs.");
    toast("USB copy failed.", "error");
    logUiError("usb_copy_failed", String(err || ""));
  }
}

async function syncUsbNow() {
  const drive = getSelectedUsbDrive();
  const localPath = getUsbLocalPath();
  setUsbSyncStatus("Sync requested...");
  try {
    const result = await api.usbSync({ drive, local_path: localPath });
    if (result?.log) {
      setUsbSyncStatus(`Sync started. Log: ${result.log}`);
    } else if (result?.message) {
      setUsbSyncStatus(result.message);
    } else {
      setUsbSyncStatus("Sync started.");
    }
    toast("USB sync started.", "info");
  } catch (err) {
    setUsbSyncStatus("USB sync failed. Check logs.");
    toast("USB sync failed.", "error");
    logUiError("usb_sync_failed", String(err || ""));
  }
}

async function flushStateOnExit() {
  try {
    saveSettings();
    saveAudioSettings();
    saveUserHistory();
  } catch (err) {
    logUiError("exit_flush_failed", String(err || ""));
  }
}

async function refreshUsbSyncStatus() {
  try {
    const status = await api.usbSyncStatus();
    if (status && status.running) {
      setUsbSyncStatus("Sync running...");
      return;
    }
    if (status && status.last_sync) {
      setUsbSyncStatus(`Last sync: ${status.last_sync}`);
      return;
    }
  } catch {
    // ignore
  }
  setUsbSyncStatus("Sync idle.");
}

async function refreshRemoteStatus() {
  try {
    const status = await api.remoteStatus();
    if (!status || !status.enabled) {
      setRemoteStatus("Remote access is off.");
      setRemoteLinks([]);
      return;
    }
    const links = Array.isArray(status.links) ? status.links : [];
    setRemoteLinks(links);
    const hint = status.message || "Remote access enabled.";
    setRemoteStatus(hint);
  } catch (err) {
    setRemoteStatus("Remote status unavailable.");
    setRemoteLinks([]);
    logUiError("remote_status_failed", String(err || ""));
  }
}

async function refreshRemoteTunnelStatus() {
  try {
    const status = await api.remoteTunnelStatus();
    const running = Boolean(status && status.running);
    const url = status && status.url ? status.url : "";
    const error = status && status.error ? status.error : "";
    const message =
      error ||
      (status && status.message
        ? status.message
        : running
          ? "Tunnel running."
          : "Tunnel idle.");
    state.remoteTunnel = { running, url };
    setRemoteTunnelStatus(message);
    setRemoteTunnelLink(url);
  } catch (err) {
    state.remoteTunnel = { running: false, url: "" };
    setRemoteTunnelStatus("Tunnel status unavailable.");
    setRemoteTunnelLink("");
    logUiError("remote_tunnel_status_failed", String(err || ""));
  }
}

async function startRemoteTunnel() {
  setRemoteTunnelStatus("Starting tunnel...");
  try {
    const result = await api.remoteTunnelStart();
    if (result && result.status) {
      const status = result.status;
      state.remoteTunnel = {
        running: Boolean(status.running),
        url: status.url || "",
      };
      setRemoteTunnelStatus(status.message || "Tunnel starting...");
      setRemoteTunnelLink(status.url || "");
    } else {
      await refreshRemoteTunnelStatus();
    }
    toast("Tunnel start requested.", "info");
  } catch (err) {
    setRemoteTunnelStatus("Tunnel start failed.");
    toast("Tunnel start failed.", "error");
    logUiError("remote_tunnel_start_failed", String(err || ""));
  }
}

async function stopRemoteTunnel() {
  setRemoteTunnelStatus("Stopping tunnel...");
  try {
    const result = await api.remoteTunnelStop();
    if (result && result.status) {
      const status = result.status;
      state.remoteTunnel = {
        running: Boolean(status.running),
        url: status.url || "",
      };
      setRemoteTunnelStatus(status.message || "Tunnel stopped.");
      setRemoteTunnelLink(status.url || "");
    } else {
      await refreshRemoteTunnelStatus();
    }
    toast("Tunnel stopped.", "info");
  } catch (err) {
    setRemoteTunnelStatus("Tunnel stop failed.");
    toast("Tunnel stop failed.", "error");
    logUiError("remote_tunnel_stop_failed", String(err || ""));
  }
}

function openRemoteUi() {
  const tunnelEl = $("remote-tunnel-link");
  if (tunnelEl) {
    const tunnelLink = tunnelEl.querySelector("a");
    if (tunnelLink && tunnelLink.href) {
      window.open(tunnelLink.href, "_blank", "noopener");
      return;
    }
  }
  const linksEl = $("remote-links");
  if (linksEl) {
    const first = linksEl.querySelector("a");
    if (first && first.href) {
      window.open(first.href, "_blank", "noopener");
      return;
    }
  }
  const host = getRemoteHost();
  if (host) {
    const url = host.startsWith("http") ? host : `http://${host}`;
    window.open(url, "_blank", "noopener");
    return;
  }
  toast("No remote link available.", "warn");
}

function setSettingsTab(tabId) {
  const buttons = Array.from(document.querySelectorAll(".settings-tab-btn"));
  const tabs = Array.from(document.querySelectorAll(".settings-tab"));
  if (!buttons.length || !tabs.length) {
    return;
  }
  const fallback = buttons[0].dataset.tab;
  const target = tabId || fallback;
  tabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === target);
  });
  buttons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === target);
  });
  if (target) {
    try {
      localStorage.setItem(SETTINGS_TAB_KEY, target);
    } catch {
      // ignore
    }
  }
}

function initSettingsTabs() {
  const buttons = Array.from(document.querySelectorAll(".settings-tab-btn"));
  if (!buttons.length) {
    return;
  }
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      setSettingsTab(button.dataset.tab);
    });
  });
  let saved = "";
  try {
    saved = localStorage.getItem(SETTINGS_TAB_KEY) || "";
  } catch {
    saved = "";
  }
  setSettingsTab(saved || buttons[0].dataset.tab);
}

function openUserModal() {
  const modal = $("new-user-modal");
  if (modal) {
    modal.classList.remove("hidden");
  }
}

function closeUserModal() {
  const modal = $("new-user-modal");
  if (modal) {
    modal.classList.add("hidden");
  }
}

function getOrbMenuItems() {
  return [
    {
      id: "wake",
      label: "Wake Systems",
      detail: "Bring the core online",
      keywords: ["wake", "start", "online"],
      action: () => wakeSystems(),
    },
    {
      id: "sleep",
      label: "Sleep Systems",
      detail: "Stand down and mute",
      keywords: ["sleep", "standby", "mute"],
      action: () => sleepSystems(),
    },
    {
      id: "settings",
      label: "Settings",
      detail: "System configuration",
      keywords: ["settings", "config", "system"],
      action: () => toggleSettings(true),
    },
    {
      id: "customize",
      label: "Customize UI",
      detail: "Theme and visuals",
      keywords: ["theme", "colors", "ui"],
      action: () => toggleCustomize(true),
    },
    {
      id: "files",
      label: "Files",
      detail: "Open file browser",
      keywords: ["files", "storage", "browse"],
      action: () => openFileBrowser(),
    },
    {
      id: "logs",
      label: "Open Logs",
      detail: "Review system logs",
      keywords: ["logs", "errors", "history"],
      action: () => openLogs(),
    },
    {
      id: "selfcheck",
      label: "Self-check",
      detail: "Run diagnostics",
      keywords: ["selfcheck", "diagnostics", "health"],
      action: () => selfCheck(),
    },
    {
      id: "chat",
      label: "Chat Interface",
      detail: "Show chat panel",
      keywords: ["chat", "assistant", "message"],
      action: () => togglePanel("panel-chat", true),
    },
    {
      id: "system",
      label: "System Diagnostics",
      detail: "Show system panel",
      keywords: ["system", "diagnostics", "cpu"],
      action: () => togglePanel("panel-system", true),
    },
    {
      id: "perf",
      label: "Performance Tracker",
      detail: "View perf stats",
      keywords: ["performance", "perf", "stats"],
      action: () => {
        state.settings.showPerf = true;
        saveSettings();
        togglePanel("panel-perf", true);
        refreshPerfReport();
      },
    },
    {
      id: "frequency",
      label: "Frequency Hub",
      detail: "Open frequency analysis",
      keywords: ["frequency", "analysis", "spectrum"],
      action: () => setActiveModule("frequency"),
    },
    {
      id: "audio",
      label: "Audio Lab",
      detail: "Open audio controls",
      keywords: ["audio", "eq", "voice"],
      action: () => setActiveModule("audio"),
    },
    {
      id: "artificer",
      label: "Artificer",
      detail: "Prototype new builds",
      keywords: ["artificer", "invent", "prototype"],
      action: () => setActiveModule("artificer"),
    },
  ];
}

function openOrbMenu() {
  const menu = $("orb-menu");
  if (!menu) {
    return;
  }
  menu.classList.add("active");
  menu.classList.remove("hidden");
  renderOrbMenuResults("");
  const input = $("orb-menu-search");
  if (input) {
    input.value = "";
    input.focus();
  }
}

function closeOrbMenu() {
  const menu = $("orb-menu");
  if (!menu) {
    return;
  }
  menu.classList.remove("active");
  menu.classList.add("hidden");
}

function renderOrbMenuResults(query) {
  const results = $("orb-menu-results");
  if (!results) {
    return;
  }
  const q = String(query || "").trim().toLowerCase();
  const items = getOrbMenuItems();
  const filtered = q
    ? items.filter((item) => {
        const haystack = [item.label, item.detail, ...(item.keywords || [])]
          .join(" ")
          .toLowerCase();
        return haystack.includes(q);
      })
    : items;
  results.innerHTML = "";
  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "orb-menu-item";
    empty.textContent = "No matches.";
    results.appendChild(empty);
    if (q) {
      const ask = document.createElement("button");
      ask.className = "orb-menu-item";
      ask.innerHTML = `<span>Ask AI</span><small>Send "${q}" to chat</small>`;
      ask.addEventListener("click", () => {
        const input = $("chat-input");
        if (input) {
          input.value = q;
        }
        closeOrbMenu();
        sendChat();
      });
      results.appendChild(ask);
    }
    return;
  }
  filtered.forEach((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "orb-menu-item";
    btn.innerHTML = `<span>${item.label}</span><small>${item.detail || ""}</small>`;
    btn.addEventListener("click", () => {
      closeOrbMenu();
      try {
        item.action();
      } catch (error) {
        logUiError("orb_menu_action_failed", error?.message || String(error));
      }
    });
    results.appendChild(btn);
  });
}

function wireSettings() {
  const audioBindings = [
    ["setting-system-sounds", "systemSounds"],
    ["setting-voice-feedback", "voiceFeedback"],
    ["setting-reply-chime", "replyChime"],
    ["setting-hush", "hush"],
    ["setting-system-alerts", "systemAlerts"],
    ["setting-process-warnings", "processWarnings"],
    ["setting-update-notices", "updateNotices"],
  ];
  audioBindings.forEach(([id, key]) => {
    const el = $(id);
    if (!el) {
      logUiError("ui_missing_setting", id);
      return;
    }
    el.addEventListener("change", (event) => {
      state.audioSettings[key] = event.target.checked;
      saveAudioSettings();
      safeText(
        "orb-audio",
        state.audioSettings.voiceFeedback ? "Voice: enabled" : "Voice: muted"
      );
    });
  });

    const uiBindings = [
      ["setting-login-enabled", "loginEnabled"],
      ["setting-show-chat", "showChat"],
      ["setting-show-system", "showSystem"],
      ["setting-show-frequency", "showFrequency"],
      ["setting-show-orbtools", "showOrbTools"],
      ["setting-show-audio", "showAudio"],
      ["setting-show-perf", "showPerf"],
      ["setting-emotion-prompts", "emotionPromptEnabled"],
      ["setting-performance-focus", "performanceFocusEnabled"],
      ["setting-usb-local-boot", "usbLocalBootEnabled"],
      ["setting-remote-enabled", "remoteUiEnabled"],
      ["setting-remote-tunnel", "remoteTunnelEnabled"],
      ["setting-desktop-view", "desktopViewEnabled"],
    ];
  uiBindings.forEach(([id, key]) => {
    const el = $(id);
    if (!el) {
      logUiError("ui_missing_setting", id);
      return;
    }
    el.addEventListener("change", (event) => {
      state.settings[key] = event.target.checked;
      saveSettings();
      if (key === "loginEnabled") {
        state.locked = Boolean(state.settings.loginEnabled);
        applyLockState();
      }
      if (key === "desktopViewEnabled") {
        toast("Desktop view updated. Relaunch UI to apply.", "info");
      }
      if (key === "remoteTunnelEnabled") {
        if (state.settings.remoteTunnelEnabled) {
          startRemoteTunnel();
        } else {
          stopRemoteTunnel();
        }
      }
      applyPanelVisibility();
    });
  });

  on("setting-volume", "input", (event) => {
    state.audioSettings.volume = parseInt(event.target.value, 10);
    saveAudioSettings();
  });
  on("setting-chime", "input", (event) => {
    state.audioSettings.chimeVolume = parseInt(event.target.value, 10);
    saveAudioSettings();
  });
  on("setting-voice", "change", (event) => {
    state.audioSettings.voice = event.target.value;
    saveAudioSettings();
  });
  on("setting-rate", "change", (event) => {
    state.audioSettings.rate = event.target.value;
    saveAudioSettings();
  });
  on("setting-pitch", "change", (event) => {
    state.audioSettings.pitch = event.target.value;
    saveAudioSettings();
  });
  on("setting-login-user", "input", (event) => {
    state.settings.loginUser = event.target.value.trim();
    saveSettings();
    applyLockState();
  });
  on("setting-login-pass", "input", (event) => {
    state.settings.loginPass = event.target.value;
    saveSettings();
  });
  on("setting-usb-local-path", "input", (event) => {
    state.settings.usbLocalBootPath = event.target.value.trim();
    saveSettings();
  });
  on("usb-copy-preset", "change", (event) => {
    applyUsbPreset(event.target.value);
  });
  on("usb-include-os", "change", (event) => {
    state.settings.usbIncludeOs = event.target.checked;
    saveSettings();
    syncUsbPresetUI();
  });
  on("usb-include-app", "change", (event) => {
    state.settings.usbIncludeApp = event.target.checked;
    updateUsbPresetFromSelection();
    saveSettings();
  });
  on("usb-include-memory", "change", (event) => {
    state.settings.usbIncludeMemory = event.target.checked;
    updateUsbPresetFromSelection();
    saveSettings();
  });
  on("usb-include-user", "change", (event) => {
    state.settings.usbIncludeUserData = event.target.checked;
    updateUsbPresetFromSelection();
    saveSettings();
  });
  on("setting-remote-host", "input", (event) => {
    state.settings.remoteUiHost = event.target.value.trim();
    saveSettings();
  });
  on("setting-ai-name", "input", (event) => {
    state.settings.aiName = event.target.value.trim();
    saveSettings();
  });
  on("setting-active-user", "change", (event) => {
    const selected = event.target.value;
    if (selected && selected !== state.activeUserId) {
      setActiveUser(selected, { lockMode: "lock", persist: true, renderHistory: true });
    }
  });
  on("new-user-open", "click", () => {
    openUserModal();
  });
  on("new-user-close", "click", () => {
    closeUserModal();
  });
  on("new-user-cancel", "click", () => {
    closeUserModal();
  });
  on("new-user-modal", "click", (event) => {
    if (event.target && event.target.id === "new-user-modal") {
      closeUserModal();
    }
  });
  on("new-user-create", "click", async () => {
    const nameInput = $("new-user-name");
    const passInput = $("new-user-pass");
    const aiInput = $("new-user-ai");
    const username = nameInput ? nameInput.value.trim() : "";
    const password = passInput ? passInput.value : "";
    const aiName = aiInput ? aiInput.value.trim() : "";
    if (!username) {
      toast("Username required.", "warn");
      return;
    }
    if (!password) {
      toast("Password required.", "warn");
      return;
    }
    const ok = await ensureAdminUnlocked();
    if (!ok) {
      return;
    }
    const exists = state.userStore.users.some(
      (user) => (user.settings?.loginUser || "").toLowerCase() === username.toLowerCase()
    );
    if (exists) {
      toast("User already exists.", "warn");
      return;
    }
    let newId = buildUserId(username);
    while (state.userStore.users.some((user) => user.id === newId)) {
      newId = buildUserId(username);
    }
    const settings = normalizeUserSettings({
      loginUser: username,
      loginPass: password,
      aiName: aiName || defaults.aiName,
    });
    state.userStore.users.push({
      id: newId,
      settings,
      createdAt: new Date().toISOString(),
    });
    saveUserStore();
    if (nameInput) nameInput.value = "";
    if (passInput) passInput.value = "";
    if (aiInput) aiInput.value = "";
    setActiveUser(newId, {
      lockMode: "lock",
      persist: true,
      renderHistory: false,
      loadHistory: false,
      deferHydration: true,
    });
    toast("User created. Unlock to continue.", "info");
    closeUserModal();
  });

  on("display-refresh", "click", () => {
    refreshDisplayMonitors();
  });

  on("usb-drive-refresh", "click", () => {
    refreshUsbDrives();
  });
  on("usb-open", "click", () => {
    openUsbDrive();
  });
  on("usb-copy", "click", () => {
    copyProjectToUsb();
  });
  on("usb-local-open", "click", () => {
    openLocalUsbPath();
  });
  on("usb-sync", "click", () => {
    syncUsbNow();
  });
  on("remote-refresh", "click", () => {
    refreshRemoteStatus();
  });
  on("remote-open", "click", () => {
    openRemoteUi();
  });
  on("remote-tunnel-start", "click", () => {
    startRemoteTunnel();
  });
  on("remote-tunnel-stop", "click", () => {
    stopRemoteTunnel();
  });

  const themeFields = [
    ["setting-theme-bg", "setting-theme-bg-color", "bg", defaults.theme.bg],
    ["setting-theme-panel", "setting-theme-panel-color", "panel", defaults.theme.panel],
    [
      "setting-theme-panel-border",
      "setting-theme-panel-border-color",
      "panelBorder",
      defaults.theme.panelBorder,
    ],
    ["setting-theme-accent", "setting-theme-accent-color", "accent", defaults.theme.accent],
    [
      "setting-theme-accent-strong",
      "setting-theme-accent-strong-color",
      "accentStrong",
      defaults.theme.accentStrong,
    ],
    [
      "setting-theme-accent-soft",
      "setting-theme-accent-soft-color",
      "accentSoft",
      defaults.theme.accentSoft,
    ],
    ["setting-theme-text", "setting-theme-text-color", "text", defaults.theme.text],
    ["setting-theme-muted", "setting-theme-muted-color", "muted", defaults.theme.muted],
  ];
  themeFields.forEach(([textId, colorId, key, fallback]) => {
    on(textId, "change", (event) => {
      const value = event.target.value.trim();
      state.settings.theme = { ...state.settings.theme, [key]: value };
      const colorEl = $(colorId);
      if (colorEl) {
        colorEl.value = colorToHex(value, fallback);
      }
      applyTheme();
      saveSettings();
      const target = $("theme-wheel-target");
      if (target && target.value === key) {
        syncThemeWheel();
      }
    });
    on(colorId, "input", (event) => {
      const value = event.target.value;
      const textEl = $(textId);
      if (textEl) {
        textEl.value = value;
      }
      state.settings.theme = { ...state.settings.theme, [key]: value };
      applyTheme();
      saveSettings();
      const target = $("theme-wheel-target");
      if (target && target.value === key) {
        syncThemeWheel();
      }
    });
  });

  on("theme-wheel-target", "change", () => {
    syncThemeWheel();
  });
  on("theme-wheel-picker", "input", (event) => {
    const target = $("theme-wheel-target");
    const hexOut = $("theme-wheel-hex");
    const value = event.target.value;
    if (hexOut) {
      hexOut.value = value;
    }
    if (target) {
      applyWheelColor(target.value, value);
    }
  });

  on("settings-apply", "click", () => {
    state.settings.theme = normalizeTheme(state.settings.theme);
    applyTheme();
    applyPanelVisibility();
    state.locked = Boolean(state.settings.loginEnabled);
    applyLockState();
    saveSettings();
    toast("Settings applied.", "info");
  });
  on("customize-apply", "click", () => {
    state.settings.theme = normalizeTheme(state.settings.theme);
    applyTheme();
    saveSettings();
    toast("Theme applied.", "info");
  });

  on("settings-relaunch", "click", () => {
    rebootProject();
  });
  on("settings-reboot", "click", () => {
    rebootProject();
  });

  initSettingsTabs();
}

function wireAudioLab() {
  on("audio-eq-target", "change", (event) => {
    state.audioEqTarget = event.target.value || "output";
    renderAudioEqList();
  });
  on("audio-eq-apply", "click", applyAudioEqSystem);
  on("audio-eq-flat", "click", resetAudioEqFlat);
  on("audio-eq-config-path", "change", (event) => {
    state.audioSettings.eqApoConfigPath = event.target.value.trim();
    saveAudioSettings();
    refreshAudioEqEngine();
  });
  on("audio-media-source", "change", (event) => {
    state.audioSettings.mediaSource = event.target.value;
    saveAudioSettings();
    renderAudioMedia();
  });
  on("audio-spotify-load", "click", applySpotifyUrl);
  on("audio-spotify-play", "click", () => {
    if (!requireUnlocked()) return;
    spotifyPlayFromUrl();
  });
  on("audio-spotify-clear", "click", clearSpotifyUrl);
  on("audio-spotify-url", "change", applySpotifyUrl);
  on("audio-spotify-url", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applySpotifyUrl();
    }
  });
  on("spotify-connect", "click", () => {
    if (!requireUnlocked()) return;
    connectSpotify();
  });
  on("spotify-disconnect", "click", () => {
    if (!requireUnlocked()) return;
    disconnectSpotify();
  });
  on("spotify-play", "click", () => {
    if (!requireUnlocked()) return;
    spotifyPlayResume();
  });
  on("spotify-pause", "click", () => {
    if (!requireUnlocked()) return;
    spotifyPause();
  });
  on("spotify-next", "click", () => {
    if (!requireUnlocked()) return;
    spotifyNext();
  });
  on("spotify-prev", "click", () => {
    if (!requireUnlocked()) return;
    spotifyPrevious();
  });
  on("spotify-transfer", "click", () => {
    if (!requireUnlocked()) return;
    spotifyTransferDevice();
  });
  on("spotify-volume", "change", (event) => {
    if (!requireUnlocked()) return;
    const volume = parseInt(event.target.value, 10);
    api.spotifyVolume({ volume: Number.isNaN(volume) ? 50 : volume }).catch(() => {});
  });
  on("spotify-shuffle", "change", (event) => {
    if (!requireUnlocked()) return;
    api.spotifyShuffle({ enabled: event.target.checked }).catch(() => {});
  });
  on("spotify-repeat", "change", (event) => {
    if (!requireUnlocked()) return;
    api.spotifyRepeat({ mode: event.target.value }).catch(() => {});
  });
  on("audio-profile-apply", "click", applyAudioProfile);
  on("audio-profile-save", "click", saveAudioProfile);
  on("audio-exam-start", "click", () => {
    if (!requireUnlocked()) return;
    startAudioExam();
  });
  on("audio-exam-stop", "click", () => {
    if (!requireUnlocked()) return;
    stopAudioExam();
  });
  on("audio-hearing-target", "change", (event) => {
    state.audioHearingTest.target = event.target.value || "output";
  });
  on("audio-hearing-start", "click", () => {
    if (!requireUnlocked()) return;
    startHearingTest();
  });
  on("audio-hearing-repeat", "click", () => {
    if (!requireUnlocked()) return;
    playHearingTone();
  });
  on("audio-hearing-stop", "click", () => {
    if (!requireUnlocked()) return;
    stopHearingTest();
  });
  on("audio-hearing-yes", "click", () => recordHearingResponse("yes"));
  on("audio-hearing-no", "click", () => recordHearingResponse("no"));
  on("audio-hearing-pleasant", "click", () => recordHearingResponse("pleasant"));
  on("audio-hearing-neutral", "click", () => recordHearingResponse("neutral"));
  on("audio-hearing-unpleasant", "click", () => recordHearingResponse("unpleasant"));
  on("audio-speech-start", "click", () => {
    if (!requireUnlocked()) return;
    startSpeechTest();
  });
  on("audio-speech-play", "click", () => {
    if (!requireUnlocked()) return;
    playSpeechPhrase();
  });
  on("audio-speech-submit", "click", () => {
    if (!requireUnlocked()) return;
    const input = $("audio-speech-input");
    submitSpeechResponse(input ? input.value : "");
  });
  on("audio-speech-input", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (!requireUnlocked()) return;
      submitSpeechResponse(event.target.value);
    }
  });
  on("audio-speech-record", "click", () => {
    if (!requireUnlocked()) return;
    recordSpeechRepeat();
  });
  on("audio-voice-calibrate", "click", () => {
    if (!requireUnlocked()) return;
    runVoiceCalibration();
  });
  on("audio-profile-apply-output", "click", () => applySuggestedEq("output"));
  on("audio-profile-apply-input", "click", () => applySuggestedEq("input"));
  on("audio-profile-save-lab", "click", () => {
    if (!requireUnlocked()) return;
    saveAudioProfileLab();
  });
  const prefBindings = [
    ["audio-pref-warmth", "audio-pref-warmth-value", "warmth"],
    ["audio-pref-clarity", "audio-pref-clarity-value", "clarity"],
    ["audio-pref-air", "audio-pref-air-value", "air"],
    ["audio-pref-bass", "audio-pref-bass-value", "bass"],
  ];
  prefBindings.forEach(([inputId, valueId, key]) => {
    on(inputId, "input", (event) => {
      const value = clampNumber(event.target.value, -10, 10, 0);
      state.audioProfilePrefs[key] = value;
      const valueEl = $(valueId);
      if (valueEl) {
        valueEl.textContent = String(value);
      }
      saveAudioProfilePrefs(state.activeUserId);
      refreshSuggestedEqFromPrefs();
    });
  });
  on("audio-master-volume", "input", (event) => {
    const value = parseInt(event.target.value, 10);
    state.audioMaster.volume = Number.isNaN(value) ? state.audioMaster.volume : value;
    const label = $("audio-master-value");
    if (label) {
      label.textContent = `${state.audioMaster.volume}%`;
    }
  });
  on("audio-master-volume", "change", (event) => {
    const value = parseInt(event.target.value, 10);
    api
      .audioSystemMasterSet({
        direction: "output",
        volume: clampNumber(value, 0, 100, state.audioMaster.volume) / 100,
      })
      .catch(() => {});
  });
  on("audio-master-mute", "change", (event) => {
    state.audioMaster.mute = event.target.checked;
    api
      .audioSystemMasterSet({ direction: "output", mute: event.target.checked })
      .catch(() => {});
  });
}

function wirePerfPanel() {
  on("btn-perf", "click", () => {
    if (!requireUnlocked()) return;
    state.settings.showPerf = true;
    saveSettings();
    togglePanel("panel-perf", true);
    refreshPerfReport({ log: true, source: "manual" });
  });
  on("perf-refresh", "click", () => {
    refreshPerfReport({ log: true, source: "manual" });
  });
  on("perf-copy", "click", async () => {
    const text = state.perfStats.lastReport || $("perf-report")?.textContent || "";
    if (!text) {
      toast("No perf report to copy.", "warn");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast("Perf report copied.", "info");
    } catch (error) {
      logUiError("perf_copy_failed", error?.message || String(error));
      toast("Copy failed.", "warn");
    }
  });
}

function setFrequencyAnalyzing(active) {
  state.freqAnalyzing = Boolean(active);
  const btn = $("freq-analyze");
  if (btn) {
    btn.disabled = state.freqAnalyzing || !state.freqFile;
    btn.textContent = state.freqAnalyzing ? "Analyzing..." : "Analyze";
  }
}

function renderFrequencyMessage(message) {
  const list = $("freq-peaks");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  const note = document.createElement("div");
  note.className = "freq-empty";
  note.textContent = message;
  list.appendChild(note);
}

function clearFrequencySummary() {
  [
    "freq-main",
    "freq-low",
    "freq-high",
    "freq-centroid",
    "freq-rolloff",
    "freq-duration",
    "freq-sr",
    "freq-emotion-suggest",
  ].forEach((id) => safeText(id, "--"));
}

function drawFrequencySpectrum(spectrum, markers = {}) {
  const canvas = $("freq-spectrum");
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }
  const cssWidth = canvas.clientWidth || canvas.width || 1;
  const cssHeight = canvas.clientHeight || canvas.height || 1;
  const dpr = window.devicePixelRatio || 1;
  const targetWidth = Math.max(1, Math.floor(cssWidth * dpr));
  const targetHeight = Math.max(1, Math.floor(cssHeight * dpr));
  if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
    canvas.width = targetWidth;
    canvas.height = targetHeight;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const padding = 10;
  const width = Math.max(1, cssWidth - padding * 2);
  const height = Math.max(1, cssHeight - padding * 2);
  if (!Array.isArray(spectrum) || spectrum.length === 0) {
    ctx.fillStyle = "rgba(217, 247, 255, 0.45)";
    ctx.font = "12px Bahnschrift, \"Cascadia Code\", \"Segoe UI\", sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Awaiting analysis", cssWidth / 2, cssHeight / 2);
    return;
  }

  ctx.strokeStyle = "rgba(62, 242, 224, 0.12)";
  ctx.lineWidth = 1;
  for (let i = 1; i < 4; i += 1) {
    const y = padding + (height * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(padding + width, y);
    ctx.stroke();
  }

  const values = spectrum
    .map((point) => Number(point.db))
    .filter((value) => Number.isFinite(value));
  const minDb = values.length ? Math.min(-80, ...values) : -80;
  const maxDb = values.length ? Math.max(-10, ...values) : -10;
  const range = maxDb - minDb || 1;
  const denom = Math.max(1, spectrum.length - 1);

  ctx.beginPath();
  spectrum.forEach((point, index) => {
    const dbValue = Number(point.db);
    const db = Number.isFinite(dbValue) ? dbValue : minDb;
    const x = padding + (index / denom) * width;
    const norm = (db - minDb) / range;
    const y = padding + height - norm * height;
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.strokeStyle = "rgba(62, 242, 224, 0.75)";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.lineTo(padding + width, padding + height);
  ctx.lineTo(padding, padding + height);
  ctx.closePath();
  ctx.fillStyle = "rgba(62, 242, 224, 0.12)";
  ctx.fill();

  const minHz = Number(spectrum[0]?.hz) || 0;
  const maxHz = Number(spectrum[spectrum.length - 1]?.hz) || 1;
  const hzRange = maxHz - minHz || 1;
  const drawMarker = (hz, color) => {
    const freq = Number(hz);
    if (!Number.isFinite(freq) || freq <= 0) {
      return;
    }
    if (freq < minHz || freq > maxHz) {
      return;
    }
    const x = padding + ((freq - minHz) / hzRange) * width;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, padding);
    ctx.lineTo(x, padding + height);
    ctx.stroke();
  };
  drawMarker(markers.lowest, "rgba(217, 247, 255, 0.35)");
  drawMarker(markers.highest, "rgba(217, 247, 255, 0.35)");
  drawMarker(markers.main, "rgba(29, 232, 255, 0.8)");
}

function renderFrequencyChips(analysis) {
  const list = $("freq-peaks");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  if (!analysis) {
    renderFrequencyMessage("Import an audio file to analyze.");
    return;
  }

  const addChip = (label, value, tone) => {
    const chip = document.createElement("div");
    chip.className = tone ? `freq-chip ${tone}` : "freq-chip";
    const title = document.createElement("span");
    title.textContent = label;
    const val = document.createElement("strong");
    val.textContent = value;
    chip.appendChild(title);
    chip.appendChild(val);
    list.appendChild(chip);
  };

  addChip("File", analysis.name || "audio");
  if (Number.isFinite(Number(analysis.channels))) {
    addChip("Channels", String(analysis.channels));
  }
  if (Number.isFinite(Number(analysis.analysis_blocks)) && Number(analysis.analysis_blocks) > 0) {
    addChip("Blocks", String(analysis.analysis_blocks));
  }

  const peaks = Array.isArray(analysis.peaks) ? analysis.peaks : [];
  peaks.forEach((peak, index) => {
    const hz = formatHz(peak.hz);
    const amp = Number(peak.amplitude);
    const ampText = Number.isFinite(amp) ? amp.toFixed(3) : "--";
    addChip(`Peak ${index + 1}`, `${hz} | amp ${ampText}`);
  });

  const bands = Array.isArray(analysis.band_energy) ? analysis.band_energy.slice() : [];
  if (bands.length) {
    bands.sort((a, b) => (Number(b.energy) || 0) - (Number(a.energy) || 0));
    bands.slice(0, 4).forEach((band) => {
      const energy = Number(band.energy);
      const energyText = Number.isFinite(energy) ? energy.toFixed(2) : "--";
      const label = band.label ? `Band ${band.label}` : "Band";
      addChip(label, energyText);
    });
  }

  const matched = Array.isArray(analysis.matched_emotions) ? analysis.matched_emotions : [];
  const seen = new Set();
  matched.forEach((match) => {
    const emotion = String(match.emotion || "").trim();
    if (!emotion || seen.has(emotion)) {
      return;
    }
    seen.add(emotion);
    addChip("Match", `${emotion} @ ${formatHz(match.hz)}`, "accent");
  });
}

function clearFrequencyUI(message) {
  clearFrequencySummary();
  renderFrequencyMessage(message || "Import an audio file to analyze.");
  drawFrequencySpectrum(null);
}

function setFrequencyFile(file) {
  state.freqFile = file || null;
  state.freqAnalysis = null;
  const message = file
    ? `Loaded ${file.name}. Ready to analyze.`
    : "Import an audio file to analyze.";
  clearFrequencyUI(message);
  setFrequencyAnalyzing(false);
}

function readFrequencyLogs() {
  try {
    const raw = localStorage.getItem(FREQ_LOG_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function appendFrequencyLog(entry) {
  try {
    const logs = readFrequencyLogs();
    logs.push(entry);
    const trimmed = logs.length > 120 ? logs.slice(-120) : logs;
    localStorage.setItem(FREQ_LOG_KEY, JSON.stringify(trimmed));
  } catch {
    // ignore
  }
}

function logFrequencyEvent(code, message, extra = {}) {
  const entry = {
    ts: new Date().toISOString(),
    code,
    message,
    extra,
  };
  appendFrequencyLog(entry);
  try {
    const severity =
      code.endsWith("000") || code.endsWith("010")
        ? "info"
        : code.endsWith("110")
        ? "warn"
        : "error";
    fireAndForget(api.logIssue?.({
      code,
      message: `frequency:${message}`,
      detail: JSON.stringify(entry),
      severity,
      source: "ui",
      context: extra,
    }));
    fireAndForget(api.logClient?.(`freq:${code}`, JSON.stringify(entry)));
  } catch {
    // ignore
  }
  return entry;
}

function parseErrorMessage(error) {
  if (!error) {
    return "";
  }
  const raw = String(error.body || error.message || error);
  if (!raw) {
    return "";
  }
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      if (parsed.detail) {
        return String(parsed.detail);
      }
      if (parsed.error) {
        return String(parsed.error);
      }
    }
  } catch {
    // ignore
  }
  return raw;
}

function classifyFrequencyError(error) {
  if (!error) {
    return { code: "PHX-FRQ-000", detail: "Unknown error." };
  }
  if (error.freqCode) {
    return { code: error.freqCode, detail: parseErrorMessage(error) || error.message || "Error." };
  }
  if (isFetchError(error)) {
    return { code: "PHX-FRQ-201", detail: "Network fetch failed." };
  }
  const status = Number(error.status || 0);
  if (status) {
    const detail = parseErrorMessage(error) || `HTTP ${status}`;
    return { code: `PHX-FRQ-${status}`, detail };
  }
  const detail = parseErrorMessage(error) || error.message || "Error.";
  return { code: "PHX-FRQ-000", detail };
}

function renderFrequencyAnalysis(analysis) {
  if (!analysis) {
    clearFrequencyUI("Import an audio file to analyze.");
    return;
  }
  safeText("freq-main", formatHz(analysis.main_frequency_hz));
  safeText("freq-low", formatHz(analysis.lowest_frequency_hz));
  safeText("freq-high", formatHz(analysis.highest_frequency_hz));
  safeText("freq-centroid", formatHz(analysis.centroid_hz));
  safeText("freq-rolloff", formatHz(analysis.rolloff_hz));
  safeText("freq-duration", formatDuration(analysis.duration_sec));
  safeText("freq-sr", formatSampleRate(analysis.sr));
  safeText("freq-emotion-suggest", analysis.suggested_emotion || "--");

  const tagInput = $("freq-tag");
  if (tagInput && !tagInput.value && analysis.main_frequency_hz) {
    tagInput.value = Math.round(Number(analysis.main_frequency_hz) || 0) || "";
  }
  const emotionInput = $("freq-emotion");
  if (emotionInput && !emotionInput.value && analysis.suggested_emotion) {
    emotionInput.value = analysis.suggested_emotion;
  }

  renderFrequencyChips(analysis);
  drawFrequencySpectrum(analysis.spectrum, {
    main: analysis.main_frequency_hz,
    lowest: analysis.lowest_frequency_hz,
    highest: analysis.highest_frequency_hz,
  });
  saveFrequencyTag({ silent: true });
}

function readFrequencyTagInputs() {
  const freqInput = $("freq-tag");
  const emotionInput = $("freq-emotion");
  const hz = freqInput ? parseFloat(freqInput.value) : 0;
  const emotion = emotionInput ? emotionInput.value.trim() : "";
  return { hz, emotion };
}

function getFileExtension(name) {
  const safe = String(name || "").trim();
  const idx = safe.lastIndexOf(".");
  if (idx <= 0) {
    return "";
  }
  return safe.slice(idx + 1).toLowerCase();
}

function shouldDecodeAudio(file) {
  if (!file) {
    return false;
  }
  const ext = getFileExtension(file.name);
  if (["mp3", "m4a", "aac", "mp4"].includes(ext)) {
    return true;
  }
  const type = String(file.type || "").toLowerCase();
  return type.includes("mpeg") || type.includes("mp4") || type.includes("aac");
}

function isFetchError(error) {
  const msg = String(error && error.message ? error.message : "");
  return /failed to fetch|networkerror|load failed/i.test(msg);
}

function writeWavString(view, offset, value) {
  for (let i = 0; i < value.length; i += 1) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}

function audioBufferToWav(audioBuffer) {
  const numChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const numFrames = audioBuffer.length;
  const bytesPerSample = 2;
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = numFrames * blockAlign;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  writeWavString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeWavString(view, 8, "WAVE");
  writeWavString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeWavString(view, 36, "data");
  view.setUint32(40, dataSize, true);

  const channels = [];
  for (let ch = 0; ch < numChannels; ch += 1) {
    channels.push(audioBuffer.getChannelData(ch));
  }
  let offset = 44;
  for (let i = 0; i < numFrames; i += 1) {
    for (let ch = 0; ch < numChannels; ch += 1) {
      let sample = channels[ch][i];
      sample = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function decodeAudioToWav(file) {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) {
    const err = new Error("Audio decode unavailable.");
    err.freqCode = "PHX-FRQ-102";
    throw err;
  }
  const arrayBuffer = await file.arrayBuffer();
  const audioCtx = new AudioCtx();
  try {
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    const wavBlob = audioBufferToWav(audioBuffer);
    return { wavBlob, audioBuffer };
  } catch (error) {
    const err = new Error(error?.message || "Audio decode failed.");
    err.freqCode = "PHX-FRQ-103";
    throw err;
  } finally {
    if (audioCtx && audioCtx.state !== "closed") {
      audioCtx.close().catch(() => {});
    }
  }
}

async function analyzeFileWithBackend(file) {
  const formData = new FormData();
  formData.append("file", file, file.name || "audio");
  return api.audioAnalyze(formData);
}

async function analyzeDecodedAudio(file) {
  const baseName = (file.name || "audio").replace(/\.[^.]+$/, "") || "audio";
  const decoded = await decodeAudioToWav(file);
  const formData = new FormData();
  formData.append("file", decoded.wavBlob, `${baseName}.wav`);
  return api.audioAnalyze(formData);
}

async function saveFrequencyTag(options = {}) {
  if (!requireUnlocked()) {
    return;
  }
  const silent = Boolean(options && options.silent);
  const { hz, emotion } = readFrequencyTagInputs();
  if (!Number.isFinite(hz) || hz <= 0 || !emotion) {
    if (!silent) {
      toast("Enter a frequency and emotion to save.", "warn");
    }
    return;
  }
  const last = state.freqTagLastSaved;
  if (
    last &&
    Number.isFinite(Number(last.hz)) &&
    Math.abs(Number(last.hz) - hz) < 0.01 &&
    String(last.emotion || "").toLowerCase() === emotion.toLowerCase()
  ) {
    return;
  }
  try {
    await api.audioEmotionTag({ hz, emotion });
    state.freqTagLastSaved = { hz, emotion: emotion.toLowerCase() };
    if (!silent) {
      toast("Frequency tag saved.", "info");
    }
  } catch (error) {
    if (!silent) {
      toast("Frequency tag save failed.", "warn");
    }
  }
}

async function runFrequencyAnalysis() {
  if (!requireUnlocked()) {
    return;
  }
  const input = $("freq-import");
  const file = state.freqFile || (input && input.files && input.files[0]);
  if (!file) {
    toast("Choose an audio file first.", "warn");
    logFrequencyEvent("PHX-FRQ-101", "No file selected.", { stage: "select" });
    return;
  }
  setFrequencyAnalyzing(true);
  const modeHint = shouldDecodeAudio(file) ? "decode-wav" : "direct";
  logFrequencyEvent("PHX-FRQ-000", "Frequency analysis requested.", {
    name: file.name,
    size: file.size,
    type: file.type,
    mode: modeHint,
    apiBase: api.baseUrl || "",
  });
  try {
    let data;
    if (shouldDecodeAudio(file)) {
      data = await analyzeDecodedAudio(file);
    } else {
      try {
        data = await analyzeFileWithBackend(file);
      } catch (error) {
        if (isFetchError(error)) {
          throw error;
        }
        logFrequencyEvent("PHX-FRQ-110", "Direct analyze failed; using decode fallback.", {
          detail: parseErrorMessage(error),
        });
        data = await analyzeDecodedAudio(file);
      }
    }
    state.freqAnalysis = data && data.analysis ? data.analysis : null;
    if (!state.freqAnalysis) {
      const err = new Error("No analysis returned.");
      err.freqCode = "PHX-FRQ-120";
      throw err;
    }
    if (state.freqAnalysis && file.name && state.freqAnalysis.name !== file.name) {
      state.freqAnalysis.name = file.name;
    }
    renderFrequencyAnalysis(state.freqAnalysis);
    logFrequencyEvent("PHX-FRQ-010", "Frequency analysis complete.", {
      main: state.freqAnalysis.main_frequency_hz,
      low: state.freqAnalysis.lowest_frequency_hz,
      high: state.freqAnalysis.highest_frequency_hz,
      suggested: state.freqAnalysis.suggested_emotion,
    });
  } catch (error) {
    const { code, detail } = classifyFrequencyError(error);
    logFrequencyEvent(code, detail || "Frequency analysis failed.", {
      stage: "analyze",
      name: file.name,
      size: file.size,
      type: file.type,
      apiBase: api.baseUrl || "",
      status: error && error.status ? error.status : undefined,
      url: error && error.url ? error.url : undefined,
    });
    const message = detail ? `${detail}` : "Frequency analysis failed.";
    toast(`Frequency analysis failed (${code}): ${message}`, "warn");
  } finally {
    setFrequencyAnalyzing(false);
  }
}

function initFrequencyHub() {
  on("freq-import", "change", (event) => {
    const file = event.target.files && event.target.files[0];
    setFrequencyFile(file || null);
  });
  on("freq-analyze", "click", () => {
    runFrequencyAnalysis();
  });
  on("freq-tag", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveFrequencyTag();
    }
  });
  on("freq-emotion", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveFrequencyTag();
    }
  });
  on("freq-tag", "change", () => {
    const { hz, emotion } = readFrequencyTagInputs();
    if (hz && emotion) {
      saveFrequencyTag();
    }
  });
  on("freq-emotion", "change", () => {
    const { hz, emotion } = readFrequencyTagInputs();
    if (hz && emotion) {
      saveFrequencyTag();
    }
  });
  window.addEventListener("resize", () => {
    if (state.freqAnalysis) {
      drawFrequencySpectrum(state.freqAnalysis.spectrum, {
        main: state.freqAnalysis.main_frequency_hz,
        lowest: state.freqAnalysis.lowest_frequency_hz,
        highest: state.freqAnalysis.highest_frequency_hz,
      });
    } else {
      drawFrequencySpectrum(null);
    }
  });
  clearFrequencyUI("Import an audio file to analyze.");
}

function initEmotionPrompt() {
  on("emotion-save", "click", () => {
    if (!requireUnlocked()) return;
    saveEmotionPrompt();
  });
  on("emotion-skip", "click", () => {
    if (!requireUnlocked()) return;
    snoozeEmotionPrompt();
  });
  on("emotion-close", "click", () => closeEmotionPrompt());
  on("emotion-input", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveEmotionPrompt();
    }
  });
}

function toggleSettings(open) {
  const panel = $("settings-panel");
  if (!panel) {
    logUiError("ui_missing_settings_panel");
    return;
  }
  if (open) {
    toggleCustomize(false);
    refreshUsbDrives();
    refreshUsbSyncStatus();
    refreshRemoteStatus();
    refreshRemoteTunnelStatus();
    refreshDisplayMonitors();
  }
  panel.classList.toggle("hidden", !open);
}

function toggleCustomize(open) {
  const panel = $("customize-panel");
  if (!panel) {
    logUiError("ui_missing_customize_panel");
    return;
  }
  if (open) {
    toggleSettings(false);
  }
  panel.classList.toggle("hidden", !open);
}

function initLayoutButtons() {
  on("btn-settings", "click", () => {
    if (!requireUnlocked()) return;
    toggleSettings(true);
  });
  on("settings-close", "click", () => toggleSettings(false));
  on("btn-customize", "click", () => {
    if (!requireUnlocked()) return;
    toggleCustomize(true);
  });
  on("btn-core-panels", "click", () => {
    state.minimal = false;
    state.autoPerfActive = false;
    state.settings.performanceFocusEnabled = false;
    state.settings.showChat = true;
    state.settings.showSystem = true;
    state.settings.showOrbTools = true;
    state.settings.showPerf = true;
    setActiveModule("core");
    saveSettings();
    applyPanelVisibility();
    toast("Core panels restored.", "info");
  });
  on("customize-close", "click", () => toggleCustomize(false));
  on("btn-files", "click", () => {
    if (!requireUnlocked()) return;
    openFileBrowser();
  });
  on("btn-minimize", "click", () => {
    if (!requireUnlocked()) return;
    state.minimal = !state.minimal;
    applyPanelVisibility();
  });
  on("btn-window-min", "click", () => {
    minimizeWindow();
  });
  on("btn-window-close", "click", () => {
    shutdownApp();
  });
  on("orb-core", "click", () => {
    if (!requireUnlocked()) return;
    openOrbMenu();
  });
  on("orb-menu-close", "click", () => {
    closeOrbMenu();
  });
  on("orb-menu", "click", (event) => {
    if (event.target && event.target.id === "orb-menu") {
      closeOrbMenu();
    }
  });
  on("orb-menu-search", "input", (event) => {
    renderOrbMenuResults(event.target.value);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeOrbMenu();
    }
  });
}

function initModuleSelect() {
  const select = $("module-select");
  if (select) {
    select.addEventListener("change", (event) => {
      setActiveModule(event.target.value || "core");
    });
  }
  on("btn-frequency", "click", () => setActiveModule("frequency"));
}

function initControls() {
  on("btn-wake", "click", () => {
    if (!requireUnlocked()) return;
    wakeSystems();
  });
  on("btn-sleep", "click", () => {
    if (!requireUnlocked()) return;
    sleepSystems();
  });
  on("btn-exit", "click", () => {
    shutdownApp();
  });
  on("btn-selfcheck", "click", () => {
    if (!requireUnlocked()) return;
    selfCheck();
  });
  on("btn-logs", "click", () => {
    if (!requireUnlocked()) return;
    openLogs();
  });
  on("btn-memory-check", "click", () => {
    if (!requireUnlocked()) return;
    memoryCheck();
  });
  on("artificer-start", "click", () => {
    toast("Artificer scaffolding only. More tools soon.", "info");
  });
  on("chat-send", "click", () => {
    if (!requireUnlocked()) return;
    sendChat();
  });
  on("audio-refresh", "click", refreshAudioDevices);
  on("audio-apply", "click", applyAudioDevices);
  on("audio-tone", "click", () => playAudioTone("sine"));
  on("audio-sweep", "click", () => playAudioTone("sweep"));
  on("audio-stop", "click", stopAudioTone);
  on("chat-input", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      sendChat();
    }
  });
  on("chat-attach", "click", () => {
    const picker = $("chat-image");
    if (picker) {
      picker.click();
    }
  });
  on("chat-image", "change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) {
      clearPendingImage();
      return;
    }
    state.pendingImageLoading = true;
    safeText("chat-attach-label", "Loading image...");
    try {
      const dataUrl = await readFileAsDataUrl(file);
      if (typeof dataUrl === "string") {
        setPendingImage(file.name, dataUrl);
      } else {
        clearPendingImage();
      }
    } catch (error) {
      clearPendingImage();
      toast("Image load failed.", "alert");
    } finally {
      state.pendingImageLoading = false;
      if (state.queuedMessage !== null) {
        const queued = state.queuedMessage;
        state.queuedMessage = null;
        const input = $("chat-input");
        if (input) {
          input.value = queued || "";
        }
        sendChat();
      }
    }
  });
}

function registerDrag(panel) {
  const header = panel.querySelector(".panel-header") || panel;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;
  let dragging = false;

  function onMouseDown(event) {
    if (event.button !== 0) {
      return;
    }
    if (event.target.closest("button, input, select, textarea")) {
      return;
    }
    event.preventDefault();
    dragging = true;
    startX = event.clientX;
    startY = event.clientY;
    startLeft = panel.offsetLeft;
    startTop = panel.offsetTop;
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp, { once: true });
  }

  function onMouseMove(event) {
    if (!dragging) {
      return;
    }
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    panel.style.left = `${startLeft + dx}px`;
    panel.style.top = `${startTop + dy}px`;
  }

  function onMouseUp() {
    dragging = false;
    document.removeEventListener("mousemove", onMouseMove);
    snapPanelToGrid(panel);
    savePanelPosition(panel);
  }

  header.addEventListener("mousedown", onMouseDown);
}

function panelStorageKey(panel) {
  const userId = state.activeUserId || "default";
  return `bjorgsun_v2_panel_${userId}_${panel.dataset.panel}`;
}

function getPanelPositions() {
  if (state.settings && typeof state.settings.panelPositions === "object") {
    return state.settings.panelPositions || {};
  }
  return {};
}

function getStoredPanelPosition(panel) {
  const key = panelStorageKey(panel);
  try {
    const raw = localStorage.getItem(key);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch {
    // ignore
  }
  const positions = getPanelPositions();
  const fallback = positions[panel.dataset.panel];
  if (fallback && typeof fallback === "object") {
    return fallback;
  }
  return null;
}

function hasStoredPosition(panel) {
  const stored = getStoredPanelPosition(panel);
  return Boolean(stored && (stored.left || stored.top || stored.width || stored.height));
}

function centerPanel(panel, offsetX = 0, offsetY = 0) {
  const padding = 20;
  const topSafe = 70;
  const rect = panel.getBoundingClientRect();
  const width = rect.width || panel.offsetWidth || 320;
  const height = rect.height || panel.offsetHeight || 240;
  const left = Math.max(padding, (window.innerWidth - width) / 2 + offsetX);
  const top = Math.max(topSafe, (window.innerHeight - height) / 2 + offsetY);
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
  panel.style.right = "auto";
  panel.style.bottom = "auto";
}

function cascadeOffset(panel) {
  const panels = Array.from(document.querySelectorAll(".panel.floating"));
  const index = Math.max(0, panels.indexOf(panel));
  const step = 28;
  const maxSteps = 6;
  const offset = (index % maxSteps) * step;
  return { x: offset, y: offset };
}

function savePanelPosition(panel) {
  const key = panelStorageKey(panel);
  const pos = {
    left: panel.style.left,
    top: panel.style.top,
    width: panel.style.width,
    height: panel.style.height,
  };
  try {
    localStorage.setItem(key, JSON.stringify(pos));
  } catch {
    // ignore
  }
  const positions = { ...getPanelPositions(), [panel.dataset.panel]: pos };
  state.settings.panelPositions = positions;
  saveSettings();
}

function restorePanelPosition(panel) {
  const pos = getStoredPanelPosition(panel);
  if (!pos) {
    return;
  }
  if (pos.left) panel.style.left = pos.left;
  if (pos.top) panel.style.top = pos.top;
  if (pos.width) panel.style.width = pos.width;
  if (pos.height) panel.style.height = pos.height;
}

function initDraggables() {
  document.querySelectorAll(".panel.floating").forEach((panel) => {
    restorePanelPosition(panel);
    clampPanel(panel);
    registerDrag(panel);
  });
  window.addEventListener("resize", clampAllPanels);
  state.layoutReady = true;
}

function initOrbAnimation() {
  const canvas = $("orb-canvas");
  if (!canvas) {
    logUiError("ui_missing_orb");
    return;
  }
  if (state.orbAnimationStarted) {
    return;
  }
  state.orbAnimationStarted = true;
  const ctx = canvas.getContext("2d");
  const textCanvas = document.createElement("canvas");
  textCanvas.width = canvas.width;
  textCanvas.height = canvas.height;
  const textCtx = textCanvas.getContext("2d");
  const imageCanvas = document.createElement("canvas");
  imageCanvas.width = canvas.width;
  imageCanvas.height = canvas.height;
  const imageCtx = imageCanvas.getContext("2d");
  const glyphSet = [".", ":", "+", "*", "o", "#", "x", "~", "-", "|"];
  const DOT_COUNT = 900;
  // Dense sand/dust swarm particles
  const dots = Array.from({ length: DOT_COUNT }, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 40 + Math.random() * 190,
    speed: 0.004 + Math.random() * 0.01,
    x: canvas.width / 2 + (Math.random() - 0.5) * 30,
    y: canvas.height / 2 + (Math.random() - 0.5) * 30,
    targetX: canvas.width / 2,
    targetY: canvas.height / 2,
    phase: Math.random() * Math.PI * 2,
    jitter: 6 + Math.random() * 14,
    vx: (Math.random() - 0.5) * 2,
    vy: (Math.random() - 0.5) * 2,
    mass: 0.6 + Math.random() * 0.8,
    size: 0.6 + Math.random() * 1.6,
    seed: Math.random() * 1000,
  }));
  const glyphs = Array.from({ length: 80 }, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 70 + Math.random() * 160,
    speed: 0.003 + Math.random() * 0.009,
    char: glyphSet[Math.floor(Math.random() * glyphSet.length)],
    phase: Math.random() * Math.PI * 2,
  }));
  state.perfStats.orb.dotCount = DOT_COUNT;
  state.perfStats.orb.glyphCount = glyphs.length;
  let textPoints = [];
  let lastThoughtKey = "";
  let lastPatternKey = "";
  let pattern = { a: 3, b: 5, amp: 110, phase: 0, rot: 0 };
  let actionPoints = [];
  let lastActionKey = "";
  let imagePoints = [];
  let lastImageKey = "";
  let imageLoading = false;
  let glyphPoints = [];
  let lastTargetKey = "";
  let targetChangedAt = 0;
  let lastDrawAt = 0;
  let lastPerfAt = 0;
  let slowFrames = 0;

  function wrapText(text, maxWidth) {
    const words = text.split(/\s+/).filter(Boolean);
    const lines = [];
    let line = "";
    words.forEach((word) => {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width <= maxWidth) {
        line = test;
      } else {
        if (line) lines.push(line);
        line = word;
      }
    });
    if (line) lines.push(line);
    return lines;
  }

  function hashString(value) {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i += 1) {
      hash ^= value.charCodeAt(i);
      hash = (hash + (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24)) >>> 0;
    }
    return hash >>> 0;
  }

  function rngFromSeed(seed) {
    let x = seed || 123456789;
    return () => {
      x ^= x << 13;
      x ^= x >>> 17;
      x ^= x << 5;
      return ((x >>> 0) % 10000) / 10000;
    };
  }

  function buildThoughtPoints(text) {
    if (!textCtx) {
      return [];
    }
    textCtx.clearRect(0, 0, textCanvas.width, textCanvas.height);
    textCtx.fillStyle = "rgba(255,255,255,1)";
    textCtx.textAlign = "center";
    textCtx.textBaseline = "middle";
    textCtx.font = "22px \"Rajdhani\", sans-serif";
    const maxWidth = 260;
    const lines = wrapText(text, maxWidth).slice(0, 5);
    const lineHeight = 26;
    const startY = textCanvas.height / 2 - (lines.length - 1) * (lineHeight / 2);
    lines.forEach((line, idx) => {
      textCtx.fillText(line, textCanvas.width / 2, startY + idx * lineHeight);
    });
    const img = textCtx.getImageData(0, 0, textCanvas.width, textCanvas.height).data;
    const points = [];
    const step = 6;
    for (let y = 0; y < textCanvas.height; y += step) {
      for (let x = 0; x < textCanvas.width; x += step) {
        const idx = (y * textCanvas.width + x) * 4 + 3;
        if (img[idx] > 120) {
          points.push({ x, y });
        }
      }
    }
    if (!points.length) {
      return [];
    }
    if (points.length > dots.length) {
      const stride = Math.ceil(points.length / dots.length);
      return points.filter((_, index) => index % stride === 0);
    }
    return points;
  }

  function samplePoints(step = 6) {
    if (!textCtx) {
      return [];
    }
    const img = textCtx.getImageData(0, 0, textCanvas.width, textCanvas.height).data;
    const points = [];
    for (let y = 0; y < textCanvas.height; y += step) {
      for (let x = 0; x < textCanvas.width; x += step) {
        const idx = (y * textCanvas.width + x) * 4 + 3;
        if (img[idx] > 120) {
          points.push({ x, y });
        }
      }
    }
    return points;
  }

  function sampleImagePoints(step = 5) {
    if (!imageCtx) {
      return [];
    }
    const img = imageCtx.getImageData(0, 0, imageCanvas.width, imageCanvas.height).data;
    const points = [];
    for (let y = 0; y < imageCanvas.height; y += step) {
      for (let x = 0; x < imageCanvas.width; x += step) {
        const idx = (y * imageCanvas.width + x) * 4;
        const r = img[idx];
        const g = img[idx + 1];
        const b = img[idx + 2];
        const a = img[idx + 3];
        if (a < 30) {
          continue;
        }
        const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
        if (lum > 0.18) {
          points.push({ x, y });
        }
      }
    }
    if (points.length > dots.length * 2) {
      const stride = Math.ceil(points.length / (dots.length * 2));
      return points.filter((_, index) => index % stride === 0);
    }
    return points;
  }

  function pickTargets() {
    const now = performance.now();
    // Highest priority: explicit override
    if (state.orbOverride && state.orbOverrideUntil > now) {
      const overrideText =
        typeof state.orbOverride === "string"
          ? state.orbOverride
          : state.orbOverride.text || state.orbOverride.mode || "override";
      glyphPoints = buildThoughtPoints(overrideText);
      return glyphPoints;
    }
    // Then any active image (vision/thought)
    if (state.orbImageDataUrl && imagePoints.length && !imageLoading) {
      return imagePoints;
    }
    // Then action glyphs
    if (actionPoints.length) {
      return actionPoints;
    }
    // Then explicit thought text glyphs
    if (textPoints.length) {
      return textPoints;
    }
    // Fallback to thought->glyph if present
    if (state.orbThought && state.orbThought !== "idle" && state.orbThought !== "processing") {
      glyphPoints = buildThoughtPoints(state.orbThought);
      return glyphPoints;
    }
    // Final fallback: use current orb state as a simple glyph target
    if (state.orbState && state.orbState !== "dormant") {
      glyphPoints = buildThoughtPoints(state.orbState);
      return glyphPoints;
    }
    return [];
  }

  function updateImagePoints() {
    if (!imageCtx) {
      imagePoints = [];
      lastImageKey = "";
      return;
    }
    if (!state.orbImageDataUrl || !state.orbImageKey) {
      imagePoints = [];
      lastImageKey = "";
      return;
    }
    if (state.orbImageKey === lastImageKey) {
      return;
    }
    lastImageKey = state.orbImageKey;
    imageLoading = true;
    const img = new Image();
    img.onload = () => {
      imageCtx.clearRect(0, 0, imageCanvas.width, imageCanvas.height);
      const maxW = imageCanvas.width * 0.7;
      const maxH = imageCanvas.height * 0.7;
      const scale = Math.min(maxW / img.width, maxH / img.height, 1);
      const w = img.width * scale;
      const h = img.height * scale;
      const x = (imageCanvas.width - w) / 2;
      const y = (imageCanvas.height - h) / 2;
      imageCtx.drawImage(img, x, y, w, h);
      imagePoints = sampleImagePoints(5);
      imageLoading = false;
    };
    img.onerror = () => {
      imagePoints = [];
      imageLoading = false;
    };
    img.src = state.orbImageDataUrl;
  }

  function buildActionPoints(action) {
    if (!textCtx) {
      return [];
    }
    const center = textCanvas.width / 2;
    textCtx.clearRect(0, 0, textCanvas.width, textCanvas.height);
    textCtx.fillStyle = "rgba(255,255,255,1)";
    textCtx.strokeStyle = "rgba(255,255,255,1)";
    textCtx.lineWidth = 4;
    const actionLower = (action || "").toLowerCase();

    if (actionLower.includes("smile") || actionLower.includes("grin") || actionLower.includes("happy")) {
      textCtx.beginPath();
      textCtx.arc(center - 50, center - 30, 10, 0, Math.PI * 2);
      textCtx.fill();
      textCtx.beginPath();
      textCtx.arc(center + 50, center - 30, 10, 0, Math.PI * 2);
      textCtx.fill();
      textCtx.beginPath();
      textCtx.arc(center, center + 20, 70, 0.1 * Math.PI, 0.9 * Math.PI);
      textCtx.stroke();
    } else if (actionLower.includes("nod")) {
      textCtx.beginPath();
      textCtx.arc(center, center - 20, 55, 0, Math.PI * 2);
      textCtx.stroke();
      textCtx.beginPath();
      textCtx.moveTo(center, center + 30);
      textCtx.lineTo(center, center + 70);
      textCtx.stroke();
      textCtx.beginPath();
      textCtx.moveTo(center - 12, center + 60);
      textCtx.lineTo(center, center + 75);
      textCtx.lineTo(center + 12, center + 60);
      textCtx.stroke();
    } else if (actionLower.includes("wave")) {
      textCtx.beginPath();
      for (let x = 0; x <= textCanvas.width; x += 10) {
        const y = center + Math.sin(x * 0.05) * 40;
        if (x === 0) {
          textCtx.moveTo(x, y);
        } else {
          textCtx.lineTo(x, y);
        }
      }
      textCtx.stroke();
    } else if (actionLower.includes("shrug")) {
      textCtx.font = "44px \"Rajdhani\", sans-serif";
      textCtx.textAlign = "center";
      textCtx.textBaseline = "middle";
      textCtx.fillText("\_(o_o)_/", center, center);
    } else {
      textCtx.font = "28px \"Rajdhani\", sans-serif";
      textCtx.textAlign = "center";
      textCtx.textBaseline = "middle";
      textCtx.fillText(action.trim(), center, center);
    }

    const points = samplePoints(6);
    if (points.length > dots.length * 2) {
      const stride = Math.ceil(points.length / (dots.length * 2));
      return points.filter((_, index) => index % stride === 0);
    }
    return points;
  }

  function updateThoughtPoints() {
    const thought = (state.orbThought || "").trim();
    const allowText =
      state.orbState === "thinking" ||
      state.orbState === "speaking" ||
      state.orbState === "listening";
    if (!allowText) {
      textPoints = [];
      lastThoughtKey = "";
      return;
    }
    if (!thought || thought === "idle" || thought === "processing") {
      textPoints = [];
      lastThoughtKey = "";
      return;
    }
    const key = `${thought}-${state.orbState}`;
    if (key !== lastThoughtKey) {
      textPoints = buildThoughtPoints(thought);
      lastThoughtKey = key;
    }
  }

  function updateActionPoints(now) {
    if (!state.orbAction || (state.orbActionUntil && now > state.orbActionUntil)) {
      actionPoints = [];
      lastActionKey = "";
      state.orbAction = "";
      return;
    }
    const key = `${state.orbAction}-${state.orbState}`;
    if (key !== lastActionKey) {
      actionPoints = buildActionPoints(state.orbAction);
      lastActionKey = key;
    }
  }

  function updatePattern() {
    const key = `${state.orbState}:${state.orbThought || ""}`;
    if (key === lastPatternKey) {
      return;
    }
    lastPatternKey = key;
    if (state.orbOverride && state.orbOverride.mode === "pattern") {
      pattern = {
        a: state.orbOverride.a || 3,
        b: state.orbOverride.b || 5,
        amp: state.orbOverride.amp || 120,
        phase: pattern.phase,
        rot: state.orbOverride.rot || pattern.rot,
      };
      return;
    }
    const seed = hashString(key || "idle");
    const rnd = rngFromSeed(seed);
    pattern = {
      a: 2 + Math.floor(rnd() * 5),
      b: 3 + Math.floor(rnd() * 6),
      amp: 90 + rnd() * 80,
      phase: rnd() * Math.PI * 2,
      rot: rnd() * Math.PI * 2,
    };
    glyphs.forEach((glyph) => {
      glyph.char = glyphSet[Math.floor(rnd() * glyphSet.length)];
      glyph.speed = 0.001 + rnd() * 0.004;
    });
  }

  function drawPattern(t, center, intensity) {
    const override = state.orbOverride && state.orbOverride.mode === "pattern";
    if (!override && !(state.orbState === "thinking" || state.orbState === "speaking" || state.orbState === "listening")) {
      return;
    }
    const steps = 220;
    const amplitude = pattern.amp * (0.6 + intensity * 0.6);
    ctx.save();
    ctx.strokeStyle = `rgba(62, 242, 224, ${0.15 + intensity * 0.2})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= steps; i += 1) {
      const theta = (i / steps) * Math.PI * 2;
      const r =
        amplitude *
        Math.sin(pattern.a * theta + pattern.phase + Math.sin(t * 0.4)) *
        (0.7 + 0.2 * Math.sin(pattern.b * theta));
      const x = center + Math.cos(theta + pattern.rot) * r;
      const y = center + Math.sin(theta + pattern.rot) * r;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.restore();
  }

  function drawWaveforms(t, center, intensity) {
    const override = state.orbOverride && state.orbOverride.mode === "waveform";
    if (!override && !(state.orbState === "listening" || state.orbState === "speaking")) {
      return;
    }
    const bands = 64;
    const baseRadius = 120;
    ctx.save();
    ctx.strokeStyle = `rgba(62, 242, 224, ${0.25 + intensity * 0.35})`;
    ctx.lineWidth = 1.5;
    for (let i = 0; i < bands; i += 1) {
      const angle = (i / bands) * Math.PI * 2;
      const wave = Math.sin(t * 4 + angle * pattern.b) * (8 + intensity * 18);
      const inner = baseRadius + wave;
      const outer = inner + 8 + intensity * 10;
      ctx.beginPath();
      ctx.moveTo(center + Math.cos(angle) * inner, center + Math.sin(angle) * inner);
      ctx.lineTo(center + Math.cos(angle) * outer, center + Math.sin(angle) * outer);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawGlyphSwarm(t, center, intensity) {
    const override = state.orbOverride && state.orbOverride.mode === "glyphs";
    const active =
      override ||
      state.orbState === "thinking" ||
      state.orbState === "speaking" ||
      state.orbState === "listening";
    ctx.save();
    const baseAlpha = active ? 0.35 + intensity * 0.35 : 0.12 + intensity * 0.15;
    ctx.fillStyle = `rgba(62, 242, 224, ${baseAlpha})`;
    ctx.font = "11px \"Rajdhani\", sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    glyphs.forEach((glyph, index) => {
      const drift = active ? 1 + intensity * 0.7 : 0.6;
      const angle = glyph.angle + t * glyph.speed * drift;
      const radius = glyph.radius + Math.sin(t * 2 + glyph.radius) * (6 + intensity * 8);
      const x = center + Math.cos(angle) * radius;
      const y = center + Math.sin(angle) * radius;
      ctx.beginPath();
      ctx.arc(x, y, active ? 2.2 : 1.4, 0, Math.PI * 2);
      ctx.fill();
      if (active && (override || state.orbState === "thinking") && index % 3 === 0) {
        ctx.fillText(glyph.char, x, y);
      }
    });
    ctx.restore();
  }

  function drawActionOverlay(t, intensity) {
    if (!actionPoints.length) {
      return;
    }
    ctx.save();
    ctx.fillStyle = `rgba(62, 242, 224, ${0.5 + intensity * 0.3})`;
    actionPoints.forEach((point, index) => {
      const jitter = Math.sin(t * 3 + index) * 1.2;
      ctx.beginPath();
      ctx.arc(point.x + jitter, point.y + jitter, 2.2, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  function drawTargetSilhouette(targets, center, intensity) {
    if (!targets.length) {
      return;
    }
    const sampleStride = Math.max(1, Math.floor(targets.length / 1200));
    ctx.save();
    ctx.fillStyle = `rgba(62, 242, 224, ${0.08 + intensity * 0.18})`;
    for (let i = 0; i < targets.length; i += sampleStride) {
      const p = targets[i];
      ctx.fillRect(p.x, p.y, 1.2, 1.2);
    }
    ctx.restore();
  }

  // Sand/dust overlay to make the swarm feel organic and alive.
  function renderDustNoise(ctx, center, targets, intensity, t) {
    const baseCount = 700;
    const count = Math.floor(baseCount * (0.6 + intensity));
    ctx.fillStyle = `rgba(62, 242, 224, ${0.06 + intensity * 0.1})`;
    for (let i = 0; i < count; i += 1) {
      const tgt =
        targets.length > 0 && i % 5 === 0
          ? targets[i % targets.length]
          : { x: center + (Math.random() - 0.5) * 360, y: center + (Math.random() - 0.5) * 360 };
      const spread = 12 + Math.random() * 26;
      const px = tgt.x + (Math.random() - 0.5) * spread * (targets.length ? 0.9 : 1.6);
      const py = tgt.y + (Math.random() - 0.5) * spread * (targets.length ? 0.9 : 1.6);
      ctx.fillRect(px, py, 1, 1);
    }
    // Light streaks to imply wind through the swarm
    ctx.strokeStyle = `rgba(62, 242, 224, ${0.05 + intensity * 0.05})`;
    for (let i = 0; i < 70; i += 1) {
      const ang = Math.random() * Math.PI * 2;
      const len = 12 + Math.random() * 24;
      const px = center + Math.cos(ang + t * 0.6) * (80 + Math.random() * 180);
      const py = center + Math.sin(ang + t * 0.6) * (80 + Math.random() * 180);
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px + Math.cos(ang) * len, py + Math.sin(ang) * len);
      ctx.stroke();
    }
  }

  function trackPerf(now) {
    if (
      state.settings.performanceFocusEnabled ||
      state.autoPerfActive ||
      state.locked ||
      state.loading ||
      state.uiHidden ||
      !state.awake
    ) {
      lastPerfAt = now;
      return;
    }
    if (state.locked || state.loading || state.uiHidden || !state.awake) {
      lastPerfAt = now;
      slowFrames = 0;
      return;
    }
    if (!lastPerfAt) {
      lastPerfAt = now;
      return;
    }
    const delta = now - lastPerfAt;
    lastPerfAt = now;
    if (delta > 90) {
      slowFrames += 1;
    } else if (slowFrames > 0) {
      slowFrames -= 1;
    }
    if (slowFrames >= 8) {
      state.autoPerfActive = true;
      applyPerfFocusClass();
      toast("Performance focus auto-enabled.", "warn");
    }
  }

  function drawStaticOrb(center, t, intensity, breathe, lockedView) {
    const ringAlpha = 0.2 + intensity * 0.4;
    ctx.strokeStyle = `rgba(62, 242, 224, ${ringAlpha})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(center, center, 150 + Math.sin(t * 0.6) * (2 + breathe * 2), 0, Math.PI * 2);
    ctx.stroke();
    if (!lockedView) {
      ctx.strokeStyle = "rgba(62, 242, 224, 0.18)";
      ctx.lineWidth = 1;
      for (let i = 0; i < 3; i += 1) {
        ctx.beginPath();
        ctx.arc(center, center, 95 + i * 18 + Math.sin(t * 1.2 + i) * 2, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  function draw(time) {
    trackPerf(time);
    const perfOrb = state.perfStats.orb;
    if (perfOrb) {
      if (perfOrb.lastFrameMs) {
        const delta = Math.max(0, time - perfOrb.lastFrameMs);
        perfOrb.avgFrameMs = perfOrb.avgFrameMs ? perfOrb.avgFrameMs * 0.9 + delta * 0.1 : delta;
        perfOrb.fps = perfOrb.avgFrameMs ? Math.min(120, 1000 / perfOrb.avgFrameMs) : 0;
      }
      perfOrb.lastFrameMs = time;
      perfOrb.frameCount += 1;
    }
    const pausedView = state.locked || state.loading || !state.awake;
    const hidden = state.uiHidden;
    if (pausedView) {
      if (!lastDrawAt || time - lastDrawAt > 900) {
        lastDrawAt = time;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const center = canvas.width / 2;
        const t = time * 0.001;
        const breathe = 0.5 + 0.5 * Math.sin(t * 0.6);
        state.orbEnergy += (state.orbEnergyTarget - state.orbEnergy) * 0.02;
        applyHeartbeatSpeed();
        drawStaticOrb(center, t, 0.25 + state.orbEnergy * 0.25, breathe, true);
      }
      setTimeout(() => draw(performance.now()), hidden ? 2000 : 1000);
      return;
    }
    const performanceFocus = Boolean(
      state.settings.performanceFocusEnabled ||
        state.autoPerfActive ||
        state.locked ||
        state.loading ||
        state.uiHidden ||
        !state.awake
    );
    const lowPower = Boolean(performanceFocus);
    const lockedView = state.locked || state.loading;
    const minFrame = lockedView
      ? 1000 / 6
      : performanceFocus
        ? 1000 / 12
        : lowPower
          ? 1000 / 18
          : 1000 / 60;
    if (minFrame && time - lastDrawAt < minFrame) {
      requestUiFrame(draw);
      return;
    }
    lastDrawAt = time;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const center = canvas.width / 2;
    const t = time * 0.001;
    const breathe = 0.5 + 0.5 * Math.sin(t * 0.6);
    state.orbEnergy += (state.orbEnergyTarget - state.orbEnergy) * 0.03;
    applyHeartbeatSpeed();
    if (!performanceFocus) {
      updateThoughtPoints();
      updateImagePoints();
      updatePattern();
      updateActionPoints(time);
    }
    if (state.orbOverrideUntil && time > state.orbOverrideUntil) {
      state.orbOverride = null;
      state.orbOverrideUntil = 0;
    }
    const thoughtLen = (state.orbThought || "").length;
    const intensity = Math.min(1, thoughtLen / 80) * (0.6 + state.orbEnergy * 0.6);
    // Handle visualization timer (lets the orb hold a thought for N seconds/heartbeats)
    const now = performance.now();
    if (state.visualization) {
      state.orbThought = state.visualization.thought.slice(0, 80);
      safeText("orb-thoughts", `Thought stream: ${state.orbThought}`);
      if (!state.visualization.done && now >= state.visualization.until) {
        state.visualization.done = true;
        state.orbOverride = null;
        state.orbOverrideUntil = 0;
        setOrbState("listening", "idle");
        state.lastVisualizationThought = state.visualization.thought;
        addChat(
          "assistant",
          `I held the image of "${state.visualization.thought}" as you asked.`
        );
        pushHistory("assistant", `[visualization] ${state.visualization.thought}`);
        state.visualization = null;
      }
    }

    if (performanceFocus) {
      drawStaticOrb(center, t, intensity, breathe, lockedView);
      setTimeout(() => draw(performance.now()), 120);
      return;
    }

    const targets = pickTargets();
    const useImage =
      (state.orbOverride && state.orbOverride.mode === "image" && imagePoints.length && !imageLoading) ||
      (!!state.orbImageDataUrl && imagePoints.length && !imageLoading);
    const targetKey = useImage
      ? state.orbImageKey || "image"
      : targets.length
        ? `t:${targets.length}:${Math.floor(targets[0].x)}:${Math.floor(targets[0].y)}`
        : state.orbAction || state.orbThought || state.orbState || "none";
    if (targetKey !== lastTargetKey) {
      lastTargetKey = targetKey;
      targetChangedAt = performance.now();
    }
    const sinceChange = performance.now() - targetChangedAt;
    const swarming = sinceChange < 1500; // ms
    const settle = sinceChange > 1200;
    const hasTargets = useImage || targets.length;
    const swarmSpeed = swarming ? 3.1 : 1.2 + state.vizReinforce * 0.1;
    const formationWeight = useImage
      ? 0.9
      : actionPoints.length
        ? 0.7
        : textPoints.length
          ? 0.6
          : targets.length
            ? 0.5
            : 0.0;

    if (!lowPower) {
      drawPattern(t, center, intensity);
      drawWaveforms(t, center, intensity);
      drawGlyphSwarm(t, center, intensity);
    } else if (!lockedView) {
      drawGlyphSwarm(t, center, intensity * 0.7);
    }
    drawActionOverlay(t, intensity);
    drawTargetSilhouette(targets, center, intensity);
    if (!lowPower) {
      renderDustNoise(ctx, center, targets, intensity, t);
    }

    const dotStep = performanceFocus ? 4 : lowPower ? 2 : 1;
    for (let i = 0; i < dots.length; i += dotStep) {
      const dot = dots[i];
      const stateBoost =
        state.orbState === "thinking"
          ? 1.45
          : state.orbState === "speaking"
            ? 1.35
            : state.orbState === "listening"
              ? 1.2
              : 1.0;
      dot.angle += dot.speed * (0.4 + stateBoost * 0.2);
      const baseRadius = dot.radius + Math.sin(t * 1.1 + dot.seed) * (18 + breathe * 8);
      const baseX = center + Math.cos(dot.angle + t * 0.08) * baseRadius;
      const baseY = center + Math.sin(dot.angle + t * 0.08) * baseRadius;

      const tgt = hasTargets ? targets[i % targets.length] : { x: baseX, y: baseY };
      const jitter =
        (Math.sin(t * 1.4 + dot.seed) + Math.cos(t * 1.1 + dot.seed * 0.7)) *
        (swarming ? 6 : 2.5);
      const targetX = (hasTargets ? tgt.x : baseX) + jitter;
      const targetY = (hasTargets ? tgt.y : baseY) + jitter;

      const pull = hasTargets ? (settle ? 0.085 : 0.055) : 0.02;
      dot.vx += (targetX - dot.x) * pull / dot.mass;
      dot.vy += (targetY - dot.y) * pull / dot.mass;

      const swirl =
        (state.orbState === "speaking"
          ? 0.09
          : state.orbState === "thinking"
            ? 0.07
            : 0.05) * (swarming ? 1.4 : 1);
      dot.vx += (-(targetY - center) / 120) * swirl;
      dot.vy += ((targetX - center) / 120) * swirl;

      const wander =
        (Math.sin(t * 0.9 + dot.seed) * 0.6 + Math.cos(t * 0.6 + dot.seed * 1.7) * 0.4) *
        (swarming ? 1.3 : 0.7);
      dot.vx += wander * 0.08;
      dot.vy += wander * 0.08;

      const damping = settle ? 0.84 : 0.91;
      dot.vx *= damping;
      dot.vy *= damping;

      const maxSpeed = (2.4 + dot.size) * stateBoost * (swarming ? 2.1 : 1.0);
      const speed = Math.hypot(dot.vx, dot.vy);
      if (speed > maxSpeed) {
        dot.vx = (dot.vx / speed) * maxSpeed;
        dot.vy = (dot.vy / speed) * maxSpeed;
      }

      dot.x += dot.vx;
      dot.y += dot.vy;

      const baseAlpha = 0.16 + state.orbEnergy * 0.55;
      const alpha =
        state.orbState === "thinking"
          ? baseAlpha + 0.16
          : state.orbState === "speaking"
            ? baseAlpha + 0.22
            : state.orbState === "listening"
              ? baseAlpha + 0.08
              : baseAlpha;
      const grainSize =
        (state.orbState === "speaking" ? 2.4 : state.orbState === "thinking" ? 2.1 : 1.6) *
        (settle ? 0.9 : 1.1);
      ctx.fillStyle = `rgba(62, 242, 224, ${alpha})`;
      ctx.fillRect(dot.x, dot.y, grainSize, grainSize);
    }

    const ringAlpha = 0.25 + state.orbEnergy * 0.6;
    ctx.strokeStyle = `rgba(62, 242, 224, ${ringAlpha})`;
    ctx.lineWidth = 2 + state.orbEnergy;
    ctx.beginPath();
    ctx.arc(
      center,
      center,
      150 + Math.sin(t * 2) * (4 + state.orbEnergy * 10) + breathe * 10,
      0,
      Math.PI * 2
    );
    ctx.stroke();

    if (state.orbState === "listening") {
      ctx.strokeStyle = "rgba(62, 242, 224, 0.25)";
      ctx.lineWidth = 1;
      for (let i = 0; i < 6; i += 1) {
        ctx.beginPath();
        ctx.arc(
          center,
          center,
          90 + i * 18 + Math.sin(t * 3 + i) * 4 + breathe * 6,
          0,
          Math.PI * 2
        );
        ctx.stroke();
      }
    }

    requestUiFrame(draw);
  }

  requestUiFrame(draw);
}

function clampPanel(panel) {
  if (!panel || panel.style.display === "none") {
    return;
  }
  const padding = 20;
  const topSafe = 70;
  const rect = panel.getBoundingClientRect();
  let width = rect.width;
  let height = rect.height;
  const maxWidth = window.innerWidth - padding * 2;
  const maxHeight = window.innerHeight - topSafe - padding;
  let left = rect.left;
  let top = rect.top;
  let changed = false;

  if (width > maxWidth) {
    width = maxWidth;
    panel.style.width = `${width}px`;
    changed = true;
  }
  if (height > maxHeight) {
    height = maxHeight;
    panel.style.height = `${height}px`;
    changed = true;
  }
  if (left < padding) {
    left = padding;
    changed = true;
  }
  if (top < topSafe) {
    top = topSafe;
    changed = true;
  }
  if (left + width > window.innerWidth - padding) {
    left = Math.max(padding, window.innerWidth - width - padding);
    changed = true;
  }
  if (top + height > window.innerHeight - padding) {
    top = Math.max(topSafe, window.innerHeight - height - padding);
    changed = true;
  }
  if (changed) {
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
  }
}

function snapPanelToGrid(panel) {
  if (!panel) {
    return;
  }
  const padding = 20;
  const topSafe = 70;
  const rect = panel.getBoundingClientRect();
  let left = rect.left;
  let top = rect.top;
  left = Math.round((left - padding) / PANEL_GRID_SIZE) * PANEL_GRID_SIZE + padding;
  top = Math.round((top - topSafe) / PANEL_GRID_SIZE) * PANEL_GRID_SIZE + topSafe;
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
  panel.style.right = "auto";
  panel.style.bottom = "auto";
  clampPanel(panel);
}

function clampAllPanels() {
  document.querySelectorAll(".panel.floating").forEach((panel) => clampPanel(panel));
}

async function pollLogs() {
  try {
    const data = await api.logsTail(20);
    const lines = data.lines || [];
    const latest = lines[lines.length - 1] || "";
    if (latest && latest !== state.lastLogLine) {
      if (/ERROR|Traceback|Exception/i.test(latest)) {
        toast(latest.slice(0, 120), "alert");
      } else if (/WARNING/i.test(latest)) {
        toast(latest.slice(0, 120), "warn");
      } else if (/update/i.test(latest)) {
        toast(latest.slice(0, 120), "update");
      }
      state.lastLogLine = latest;
    }
  } catch (error) {
    // ignore
  }
}

const PERF_LOOP_INTERVALS = {
  status: { base: 6000, slow: 15000 },
  ollama: { base: 9000, slow: 20000 },
  logs: { base: 8000, slow: 20000 },
  "audio-metrics": { base: 2500, slow: 8000 },
  spotify: { base: 9000, slow: 20000 },
  proactive: { base: 60000, slow: 120000 },
  tunnel: { base: 20000, slow: 40000 },
  perf: { base: 60000, slow: 180000 },
};

function recordLoopStat(key, durationMs) {
  if (!key) {
    return;
  }
  const loops = state.perfStats.loops || {};
  const entry = loops[key] || { runs: 0, avgMs: 0, lastMs: 0, lastAt: 0 };
  const dur = Number.isFinite(durationMs) ? Math.max(0, durationMs) : 0;
  entry.runs += 1;
  entry.lastMs = dur;
  entry.lastAt = Date.now();
  entry.avgMs = entry.avgMs ? entry.avgMs * 0.8 + dur * 0.2 : dur;
  loops[key] = entry;
  state.perfStats.loops = loops;
}

function scheduleLoop(fn, baseMs, slowMs, options = {}) {
  const { skipWhenLocked = false, skipWhenHidden = false, guardKey = "" } = options;
  const run = () => {
    const lowPower = Boolean(
      state.settings.performanceFocusEnabled ||
        state.autoPerfActive ||
        state.locked ||
        state.loading
    );
    const locked = state.locked || state.loading;
    const hidden = Boolean(state.uiHidden);
    if (!((skipWhenLocked && locked) || (skipWhenHidden && hidden))) {
      if (guardKey) {
        if (!loopGuards[guardKey]) {
          loopGuards[guardKey] = true;
          const started = performance.now();
          Promise.resolve()
            .then(fn)
            .catch(() => {})
            .finally(() => {
              recordLoopStat(guardKey, performance.now() - started);
              loopGuards[guardKey] = false;
            });
        }
      } else {
        const started = performance.now();
        Promise.resolve()
          .then(fn)
          .catch(() => {})
          .finally(() => recordLoopStat("anonymous", performance.now() - started));
      }
    }
    const delay = lowPower ? slowMs : baseMs;
    setTimeout(run, delay);
  };
  setTimeout(run, baseMs);
}

function startLoops() {
  if (state.loopsStarted) {
    return;
  }
  if (state.locked || state.loading) {
    setTimeout(startLoops, 1200);
    return;
  }
  state.loopsStarted = true;
  updateStatus();
  checkOllama();
  refreshRemoteTunnelStatus();
  scheduleLoop(updateStatus, 6000, 15000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "status",
  });
  scheduleLoop(checkOllama, 9000, 20000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "ollama",
  });
  scheduleLoop(pollLogs, 8000, 20000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "logs",
  });
  scheduleLoop(pollAudioMetrics, 2500, 8000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "audio-metrics",
  });
  scheduleLoop(refreshSpotifyStatus, 9000, 20000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "spotify",
  });
  scheduleLoop(maybeProactive, 60000, 120000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "proactive",
  });
  scheduleLoop(() => {
    if (state.settings.remoteTunnelEnabled) {
      refreshRemoteTunnelStatus();
    }
  }, 20000, 40000, {
    skipWhenLocked: true,
    skipWhenHidden: true,
    guardKey: "tunnel",
  });
  scheduleLoop(() => refreshPerfReport({ log: true, source: "auto" }), 60000, 180000, {
    skipWhenLocked: true,
    skipWhenHidden: false,
    guardKey: "perf",
  });
}

function initPostLogin() {
  if (state.postLoginReady) {
    return;
  }
  state.postLoginReady = true;
  wireSettings();
  wirePerfPanel();
  wireAudioLab();
  initFrequencyHub();
  initEmotionPrompt();
  initLayoutButtons();
  initModuleSelect();
  state.layoutReady = true;
  setActiveModule(state.activeModule);
  initControls();
  initDraggables();
  initOrbAnimation();
  setOrbState("dormant", "idle");
  updateOrbEmotionUI();
  syncWakeButtons();
}

function init() {
  if (state.uiInitialized) {
    return;
  }
  state.uiInitialized = true;
  resolveDisplayRole();
  if (state.secondaryDisplay) {
    state.loading = false;
    state.locked = true;
    applyLoadingState();
    applyLockState();
    if (document.body) {
      document.body.classList.add("secondary-idle");
    }
    return;
  }
  state.uiHidden = Boolean(document.hidden);
  document.addEventListener("visibilitychange", () => {
    state.uiHidden = Boolean(document.hidden);
    applyPerfFocusClass();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === DISPLAY_ROLE_KEY) {
      resolveDisplayRole();
      applyLockState();
    }
  });
  state.loading = true;
  applyLoadingState();
  renderLoadingChecks([]);
  updateLoadingProgress([]);
  loadSounds();
  state.localSettingsLoaded = loadSettings();
  refreshDisplayLease();
  setInterval(refreshDisplayLease, 15000);
  on("loading-retry", "click", () => runStartupChecks());
  runStartupChecks();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
