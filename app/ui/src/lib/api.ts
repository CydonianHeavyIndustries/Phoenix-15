const cfg = (window as any).__BJ_CFG || {};
const API_BASE = cfg.apiBase || "/";

async function req(path: string, opts: RequestInit = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

export async function apiAuth(username: string, password: string) {
  return req(`${API_BASE}api/auth`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function apiWake() {
  return req(`${API_BASE}api/wake`, { method: "POST" });
}

export async function apiHush(value: boolean) {
  return req(`${API_BASE}api/hush`, {
    method: "POST",
    body: JSON.stringify({ value }),
  });
}

export async function apiSelfCheck() {
  return req(`${API_BASE}api/selfcheck`, { method: "POST" });
}

export async function apiPower() {
  return req(`${API_BASE}api/power`, { method: "POST" });
}

export async function apiChat(message: string) {
  return req(`${API_BASE}api/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function apiTerminal(command: string) {
  return req(`${API_BASE}api/terminal`, {
    method: "POST",
    body: JSON.stringify({ command }),
  });
}

export async function apiSettingsGet() {
  return req(`${API_BASE}api/settings`);
}

export async function apiSettingsSet(settings: Record<string, any>) {
  return req(`${API_BASE}api/settings`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function apiLevels() {
  return req(`${API_BASE}api/levels`);
}

export async function apiDiagnostics() {
  return req(`${API_BASE}api/diagnostics`);
}

export async function apiMood() {
  return req(`${API_BASE}api/mood`);
}

export async function apiLogs() {
  return req(`${API_BASE}api/logs`);
}

export async function apiOpenLogs() {
  return req(`${API_BASE}api/open_logs`);
}
