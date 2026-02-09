const $ = (id) => document.getElementById(id);

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
    api.logClient?.(message, detail);
  } catch {
    // ignore
  }
}

function createWebApi() {
  const base =
    (window.__BJ_CFG && window.__BJ_CFG.apiBase) || "http://127.0.0.1:1326";

  async function request(path, options = {}) {
    const response = await fetch(`${base}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response.json();
  }

  async function requestBinary(path, payload) {
    const response = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response.arrayBuffer();
  }

  return {
    ping: () => request("/ping"),
    wake: () => request("/wake", { method: "POST", body: "{}" }),
    sleep: () => request("/power", { method: "POST", body: "{}" }),
    selfcheck: () => request("/selfcheck", { method: "POST", body: "{}" }),
    logsOpen: () => request("/logs/open"),
    logsTail: (lines = 20) => request(`/logs/tail?lines=${lines}`),
    filesOpen: (payload) =>
      request("/files/open", { method: "POST", body: JSON.stringify(payload || {}) }),
    memoryInfo: () => request("/memory/info"),
    memoryReload: () => request("/memory/reload", { method: "POST", body: "{}" }),
    aiLocal: (payload) =>
      request("/ai/local", { method: "POST", body: JSON.stringify(payload || {}) }),
    visionAnalyze: (payload) =>
      request("/vision/analyze", { method: "POST", body: JSON.stringify(payload || {}) }),
    tts: (payload) => requestBinary("/tts", payload || {}),
    settingsGet: () => request("/settings/get"),
    settingsSet: (payload) =>
      request("/settings/set", { method: "POST", body: JSON.stringify(payload || {}) }),
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
    logClient: (message, detail) =>
      request("/log/client", { method: "POST", body: JSON.stringify({ message, detail }) }),
  };
}

const api = window.bjorgsunApi || createWebApi();

window.addEventListener("error", (event) => {
  logUiError("ui_error", event?.message || String(event));
});

window.addEventListener("unhandledrejection", (event) => {
  logUiError("ui_rejection", event?.reason?.message || String(event?.reason || event));
});

const defaults = {
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
  showChat: true,
  showSystem: true,
  showFrequency: true,
  showOrbTools: true,
  showAudio: true,
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
  orbState: "dormant",
  orbThought: "idle",
  lastLogLine: "",
  settings: { ...defaults },
  history: [],
  minimal: false,
  orbEnergy: 0.2,
  orbEnergyTarget: 0.2,
  orbStateChangedAt: 0,
  activeModule: "core",
  audioDevicesLoaded: false,
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
};

const prompts = new Map();

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
  if (!state.settings.systemSounds) {
    return;
  }
  if (state.settings.hush && key !== "system") {
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
  if (state.settings.hush && tone !== "info") {
    return;
  }
  if (tone === "alert" && !state.settings.systemAlerts) {
    return;
  }
  if (tone === "warn" && !state.settings.processWarnings) {
    return;
  }
  if (tone === "update" && !state.settings.updateNotices) {
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

  if (tone === "alert" && state.settings.systemAlerts) {
    playSound("alert", state.settings.volume / 100);
  }
  if (tone === "warn" && state.settings.processWarnings) {
    playSound("warn", state.settings.volume / 100);
  }
  if (tone === "update" && state.settings.updateNotices) {
    playSound("update", state.settings.volume / 100);
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

function applyHeartbeatSpeed() {
  const energy = state.orbEnergy;
  const speed = state.awake ? Math.max(1.6, 4.2 - energy * 2.4) : 4.6;
  document.documentElement.style.setProperty("--heartbeat-speed", `${speed.toFixed(2)}s`);
}

function addChat(role, text) {
  const log = $("chat-log");
  if (!log) {
    return;
  }
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = text;
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
  const saved = localStorage.getItem("bjorgsun_v2_settings");
  if (saved) {
    try {
      state.settings = { ...state.settings, ...JSON.parse(saved) };
    } catch (error) {
      console.warn("Settings load failed", error);
    }
  }
  state.settings.theme = normalizeTheme(state.settings.theme);
}

function saveSettings() {
  state.settings.theme = normalizeTheme(state.settings.theme);
  localStorage.setItem("bjorgsun_v2_settings", JSON.stringify(state.settings));
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

function syncSettingsUI() {
  const mapChecked = [
    ["setting-system-sounds", "systemSounds"],
    ["setting-voice-feedback", "voiceFeedback"],
    ["setting-reply-chime", "replyChime"],
    ["setting-hush", "hush"],
    ["setting-system-alerts", "systemAlerts"],
    ["setting-process-warnings", "processWarnings"],
    ["setting-update-notices", "updateNotices"],
    ["setting-show-chat", "showChat"],
    ["setting-show-system", "showSystem"],
    ["setting-show-frequency", "showFrequency"],
    ["setting-show-orbtools", "showOrbTools"],
    ["setting-show-audio", "showAudio"],
  ];
  mapChecked.forEach(([id, key]) => {
    const el = $(id);
    if (el) {
      el.checked = Boolean(state.settings[key]);
    }
  });
  const volume = $("setting-volume");
  if (volume) {
    volume.value = state.settings.volume;
  }
  const chime = $("setting-chime");
  if (chime) {
    chime.value = state.settings.chimeVolume;
  }
  const voice = $("setting-voice");
  if (voice) {
    voice.value = state.settings.voice;
  }
  const rate = $("setting-rate");
  if (rate) {
    rate.value = state.settings.rate;
  }
  const pitch = $("setting-pitch");
  if (pitch) {
    pitch.value = state.settings.pitch;
  }

  const theme = normalizeTheme(state.settings.theme);
  const themeFields = [
    ["setting-theme-bg", "bg"],
    ["setting-theme-panel", "panel"],
    ["setting-theme-panel-border", "panelBorder"],
    ["setting-theme-accent", "accent"],
    ["setting-theme-accent-strong", "accentStrong"],
    ["setting-theme-accent-soft", "accentSoft"],
    ["setting-theme-text", "text"],
    ["setting-theme-muted", "muted"],
  ];
  themeFields.forEach(([id, key]) => {
    const el = $(id);
    if (el) {
      el.value = theme[key] || "";
    }
  });
  applyTheme();

  applyPanelVisibility();
}

function applyPanelVisibility() {
  if (state.minimal) {
    togglePanel("panel-controls", false);
    togglePanel("panel-chat", false);
    togglePanel("panel-system", false);
    togglePanel("panel-frequency", false);
    togglePanel("panel-orb-tools", false);
    togglePanel("panel-audio", false);
    return;
  }
  const showCore = state.activeModule === "core" || state.activeModule === "all";
  const showFrequency = state.activeModule === "frequency" || state.activeModule === "all";
  const showAudio = state.activeModule === "audio" || state.activeModule === "all";
  togglePanel("panel-controls", true);
  togglePanel("panel-chat", showCore && state.settings.showChat && state.awake);
  togglePanel("panel-system", showCore && state.settings.showSystem);
  togglePanel("panel-frequency", showFrequency && state.settings.showFrequency && state.awake);
  togglePanel("panel-orb-tools", showCore && state.settings.showOrbTools);
  togglePanel("panel-audio", showAudio && state.settings.showAudio);
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
}

function setActiveModule(moduleName) {
  state.activeModule = moduleName;
  const select = $("module-select");
  if (select && moduleName !== "frequency") {
    select.value = moduleName;
  }
  const freqBtn = $("btn-frequency");
  if (freqBtn) {
    freqBtn.classList.toggle("active", moduleName === "frequency");
  }
  applyPanelVisibility();
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
    await api.memoryReload();
    await api.ollamaStart();
    await api.wake();
    state.awake = true;
    setOrbState("listening", "online");
    safeText("orb-audio", state.settings.voiceFeedback ? "Voice: enabled" : "Voice: muted");
    applyPanelVisibility();
    syncWakeButtons();
    toast("Systems awake.");
    playSound("system", state.settings.volume / 100);
  } catch (error) {
    api.logClient?.("wake_failed", error?.message || String(error));
    toast("Wake failed.", "alert");
    setOrbState("dormant");
  }
}

async function sleepSystems() {
  try {
    await api.sleep();
  } catch (error) {
    toast("Sleep request failed.", "warn");
  }
  state.awake = false;
  setOrbState("dormant");
  applyPanelVisibility();
  syncWakeButtons();
  safeText("orb-audio", "Voice: muted");
}

async function shutdownApp() {
  await sleepSystems();
  try {
    window.close();
  } catch {
    // ignore
  }
}

async function selfCheck() {
  try {
    const data = await api.selfcheck();
    toast(`Self-check CPU ${Math.round(data.cpu || 0)}% / MEM ${Math.round(data.memory || 0)}%`);
  } catch (error) {
    toast("Self-check failed.", "warn");
  }
}

async function memoryCheck() {
  try {
    const info = await api.memoryInfo();
    if (!info.count || info.count < 1) {
      await api.memoryReload();
      toast("Memory injected.");
    } else {
      toast(`Memory entries: ${info.count}`);
    }
  } catch (error) {
    toast("Memory check failed.", "warn");
  }
}

async function openLogs() {
  try {
    await api.logsOpen();
    toast("Logs folder opened.");
  } catch (error) {
    toast("Logs open failed.", "warn");
  }
}

async function openFileBrowser() {
  try {
    await api.filesOpen({});
    toast("File browser opened.");
  } catch (error) {
    toast("File browser failed.", "warn");
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
  } catch (error) {
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
  } catch (error) {
    toast("Audio device update failed.", "warn");
  }
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
  if (input) {
    input.value = "";
    input.disabled = true;
  }
  const sendBtn = $("chat-send");
  if (sendBtn) {
    sendBtn.disabled = true;
  }
  state.chatBusy = true;
  const userLine = text || (state.pendingImage ? `Image: ${state.pendingImage.name}` : "");
  if (userLine) {
    addChat("user", userLine);
    state.history.push({ role: "user", content: userLine });
  }
  state.orbThought = (text || userLine).slice(0, 80);
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
          state.history.push({ role: "system", content: memoryLine });
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
    state.history.push({ role: "assistant", content: reply });
    state.orbThought = reply.slice(0, 80);
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
    if (state.settings.voiceFeedback) {
      await speakText(reply);
    } else if (state.settings.replyChime) {
      playSound("chime", state.settings.chimeVolume / 100);
    }
    setOrbState("listening", "idle");
  } catch (error) {
    addChat("assistant", "System offline. Check backend.");
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
  if (!state.settings.voiceFeedback) {
    return;
  }
  try {
    const payload = {
      text,
      voice: state.settings.voice,
      rate: state.settings.rate,
      pitch: state.settings.pitch,
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

function wireSettings() {
  const bindings = [
    ["setting-system-sounds", "systemSounds"],
    ["setting-voice-feedback", "voiceFeedback"],
    ["setting-reply-chime", "replyChime"],
    ["setting-hush", "hush"],
    ["setting-system-alerts", "systemAlerts"],
    ["setting-process-warnings", "processWarnings"],
    ["setting-update-notices", "updateNotices"],
    ["setting-show-chat", "showChat"],
    ["setting-show-system", "showSystem"],
    ["setting-show-frequency", "showFrequency"],
    ["setting-show-orbtools", "showOrbTools"],
    ["setting-show-audio", "showAudio"],
  ];
  bindings.forEach(([id, key]) => {
    const el = $(id);
    if (!el) {
      logUiError("ui_missing_setting", id);
      return;
    }
    el.addEventListener("change", (event) => {
      state.settings[key] = event.target.checked;
      saveSettings();
      applyPanelVisibility();
    });
  });

  on("setting-volume", "input", (event) => {
    state.settings.volume = parseInt(event.target.value, 10);
    saveSettings();
  });
  on("setting-chime", "input", (event) => {
    state.settings.chimeVolume = parseInt(event.target.value, 10);
    saveSettings();
  });
  on("setting-voice", "change", (event) => {
    state.settings.voice = event.target.value;
    saveSettings();
  });
  on("setting-rate", "change", (event) => {
    state.settings.rate = event.target.value;
    saveSettings();
  });
  on("setting-pitch", "change", (event) => {
    state.settings.pitch = event.target.value;
    saveSettings();
  });

  const themeFields = [
    ["setting-theme-bg", "bg"],
    ["setting-theme-panel", "panel"],
    ["setting-theme-panel-border", "panelBorder"],
    ["setting-theme-accent", "accent"],
    ["setting-theme-accent-strong", "accentStrong"],
    ["setting-theme-accent-soft", "accentSoft"],
    ["setting-theme-text", "text"],
    ["setting-theme-muted", "muted"],
  ];
  themeFields.forEach(([id, key]) => {
    on(id, "change", (event) => {
      state.settings.theme = { ...state.settings.theme, [key]: event.target.value.trim() };
      applyTheme();
      saveSettings();
    });
  });
}

function toggleSettings(open) {
  const panel = $("settings-panel");
  if (!panel) {
    logUiError("ui_missing_settings_panel");
    return;
  }
  panel.classList.toggle("hidden", !open);
}

function initLayoutButtons() {
  on("btn-settings", "click", () => toggleSettings(true));
  on("settings-close", "click", () => toggleSettings(false));
  on("btn-customize", "click", () => {
    toggleSettings(true);
    const section = $("theme-section");
    if (section) {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
  on("btn-files", "click", openFileBrowser);
  on("btn-minimize", "click", () => {
    state.minimal = !state.minimal;
    applyPanelVisibility();
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
  on("btn-wake", "click", wakeSystems);
  on("btn-sleep", "click", sleepSystems);
  on("btn-exit", "click", shutdownApp);
  on("btn-selfcheck", "click", selfCheck);
  on("btn-logs", "click", openLogs);
  on("btn-memory-check", "click", memoryCheck);
  on("chat-send", "click", sendChat);
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
  on("freq-analyze", "click", () => {
    toast("Frequency analysis queued.");
  });
}

function registerDrag(panel) {
  const header = panel;
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
    savePanelPosition(panel);
  }

  header.addEventListener("mousedown", onMouseDown);
}

function savePanelPosition(panel) {
  const key = `bjorgsun_v2_panel_${panel.dataset.panel}`;
  const pos = { left: panel.style.left, top: panel.style.top, width: panel.style.width, height: panel.style.height };
  localStorage.setItem(key, JSON.stringify(pos));
}

function restorePanelPosition(panel) {
  const key = `bjorgsun_v2_panel_${panel.dataset.panel}`;
  const raw = localStorage.getItem(key);
  if (!raw) {
    return;
  }
  try {
    const pos = JSON.parse(raw);
    if (pos.left) panel.style.left = pos.left;
    if (pos.top) panel.style.top = pos.top;
    if (pos.width) panel.style.width = pos.width;
    if (pos.height) panel.style.height = pos.height;
  } catch (error) {
    console.warn("Failed to restore panel", error);
  }
}

function initDraggables() {
  document.querySelectorAll(".panel.floating").forEach((panel) => {
    restorePanelPosition(panel);
    clampPanel(panel);
    registerDrag(panel);
  });
  window.addEventListener("resize", clampAllPanels);
}

function initOrbAnimation() {
  const canvas = $("orb-canvas");
  if (!canvas) {
    logUiError("ui_missing_orb");
    return;
  }
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
  const dots = Array.from({ length: 240 }, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 40 + Math.random() * 150,
    speed: 0.004 + Math.random() * 0.008,
    x: canvas.width / 2,
    y: canvas.height / 2,
    targetX: canvas.width / 2,
    targetY: canvas.height / 2,
    phase: Math.random() * Math.PI * 2,
    jitter: 6 + Math.random() * 10,
  }));
  const glyphs = Array.from({ length: 180 }, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 70 + Math.random() * 140,
    speed: 0.003 + Math.random() * 0.006,
    char: glyphSet[Math.floor(Math.random() * glyphSet.length)],
    phase: Math.random() * Math.PI * 2,
  }));
  let textPoints = [];
  let lastThoughtKey = "";
  let lastPatternKey = "";
  let pattern = { a: 3, b: 5, amp: 110, phase: 0, rot: 0 };
  let actionPoints = [];
  let lastActionKey = "";
  let imagePoints = [];
  let lastImageKey = "";
  let imageLoading = false;

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
      textCtx.fillText("¯\\_(ツ)_/¯", center, center);
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
    if (state.orbState !== "thinking") {
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

  function draw(time) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const center = canvas.width / 2;
    const t = time * 0.001;
    const breathe = 0.5 + 0.5 * Math.sin(t * 0.6);
    state.orbEnergy += (state.orbEnergyTarget - state.orbEnergy) * 0.03;
    applyHeartbeatSpeed();
    updateThoughtPoints();
    updateImagePoints();
    updatePattern();
    updateActionPoints(time);
    if (state.orbOverrideUntil && time > state.orbOverrideUntil) {
      state.orbOverride = null;
      state.orbOverrideUntil = 0;
    }
    const thoughtLen = (state.orbThought || "").length;
    const intensity = Math.min(1, thoughtLen / 80) * (0.6 + state.orbEnergy * 0.6);
    const useImage =
      state.orbOverride && state.orbOverride.mode === "image" && imagePoints.length && !imageLoading;

    drawPattern(t, center, intensity);
    drawWaveforms(t, center, intensity);
    drawGlyphSwarm(t, center, intensity);
    drawActionOverlay(t, intensity);

    dots.forEach((dot) => {
      const drift =
        state.orbState === "thinking"
          ? 2.2
          : state.orbState === "speaking"
            ? 1.6
            : state.orbState === "listening"
              ? 1.3
              : 1.15;
      dot.angle += dot.speed * drift;
      const wobble =
        state.orbState === "thinking"
          ? Math.sin(t * 2.6 + dot.angle * 3) * 16
          : Math.sin(t * 1.6 + dot.angle) * 8;
      const jitter = Math.sin(t * 1.4 + dot.phase) * dot.jitter;
      const radius = dot.radius + wobble + breathe * 10 + jitter;
      const orbitX = center + Math.cos(dot.angle) * radius;
      const orbitY = center + Math.sin(dot.angle) * radius;
      if (useImage) {
        const target = imagePoints[dots.indexOf(dot) % imagePoints.length];
        dot.targetX = target.x + Math.sin(t * 2 + dot.angle) * 2;
        dot.targetY = target.y + Math.cos(t * 2 + dot.angle) * 2;
      } else if (state.orbState === "thinking" && textPoints.length) {
        const target = textPoints[dots.indexOf(dot) % textPoints.length];
        dot.targetX = target.x + Math.sin(t * 2 + dot.angle) * 2;
        dot.targetY = target.y + Math.cos(t * 2 + dot.angle) * 2;
      } else {
        dot.targetX = orbitX;
        dot.targetY = orbitY;
      }
      dot.x += (dot.targetX - dot.x) * 0.12;
      dot.y += (dot.targetY - dot.y) * 0.12;
      const baseAlpha = 0.25 + state.orbEnergy * 0.5;
      const alpha =
        state.orbState === "thinking"
          ? baseAlpha + 0.1
          : state.orbState === "speaking"
            ? baseAlpha + 0.2
            : baseAlpha;
      ctx.fillStyle = `rgba(62, 242, 224, ${alpha})`;
      ctx.beginPath();
      ctx.arc(dot.x, dot.y, state.orbState === "speaking" ? 3 : 2, 0, Math.PI * 2);
      ctx.fill();
    });

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

    requestAnimationFrame(draw);
  }

  requestAnimationFrame(draw);
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

function startLoops() {
  updateStatus();
  checkOllama();
  setInterval(updateStatus, 4000);
  setInterval(checkOllama, 6000);
  setInterval(pollLogs, 5000);
  setInterval(pollAudioMetrics, 1000);
}

function init() {
  logUiError("ui_init", "renderer_loaded");
  loadSounds();
  loadSettings();
  api.settingsGet()
    .then((data) => {
      if (data) {
        state.settings = { ...state.settings, ...data };
        state.settings.theme = normalizeTheme(state.settings.theme);
      }
    })
    .catch(() => {})
    .finally(() => {
      syncSettingsUI();
      saveSettings();
    });
  wireSettings();
  initLayoutButtons();
  initModuleSelect();
  setActiveModule(state.activeModule);
  initControls();
  refreshAudioDevices();
  initDraggables();
  initOrbAnimation();
  setOrbState("dormant", "idle");
  syncWakeButtons();
  startLoops();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
