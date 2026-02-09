const { contextBridge } = require("electron");
const fs = require("fs");
const path = require("path");

const API_BASE = process.env.BJORGSUN_API || "http://127.0.0.1:1326";
const ROOT_DIR = path.join(__dirname, "..", "..");
const LOG_DIR = path.join(ROOT_DIR, "logs");
const FALLBACK_LOG = path.join(LOG_DIR, "desktop_ui.log");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
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
  const response = await fetch(`${API_BASE}${path}`, {
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

function appendFallbackLog(message, detail, error) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const stamp = new Date().toISOString();
    const line = `${stamp}Z ${message} ${detail || ""} ${error ? `err=${error}` : ""}`.trim();
    fs.appendFileSync(FALLBACK_LOG, `${line}\n`, "utf8");
  } catch (err) {
    // ignore
  }
}

contextBridge.exposeInMainWorld("bjorgsunApi", {
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
  aiLocal: (payload) => request("/ai/local", { method: "POST", body: JSON.stringify(payload || {}) }),
  tts: (payload) => requestBinary("/tts", payload || {}),
  settingsGet: () => request("/settings/get"),
  settingsSet: (payload) => request("/settings/set", { method: "POST", body: JSON.stringify(payload || {}) }),
  ollamaStatus: () => request("/ollama/status"),
  ollamaStart: () => request("/ollama/start", { method: "POST", body: "{}" }),
  audioHealth: () => request("/audio/api/health"),
  audioDevices: () => request("/audio/api/devices"),
  audioStatus: () => request("/audio/api/status"),
  audioActiveDevice: (payload) => request("/audio/api/active-device", { method: "POST", body: JSON.stringify(payload || {}) }),
  audioTone: (payload) => request("/audio/api/tone", { method: "POST", body: JSON.stringify(payload || {}) }),
  audioStop: () => request("/audio/api/stop", { method: "POST", body: "{}" }),
  audioSpectrum: () => request("/audio/api/spectrum"),
  audioEq: () => request("/audio/api/eq"),
  audioEqSet: (payload) => request("/audio/api/eq", { method: "POST", body: JSON.stringify(payload || {}) }),
  logClient: async (message, detail) => {
    try {
      return await request("/log/client", { method: "POST", body: JSON.stringify({ message, detail }) });
    } catch (error) {
      appendFallbackLog(message, detail, error?.message || String(error));
      return { ok: false };
    }
  },
});
