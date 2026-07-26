const BASE = "";
const TOKEN_KEY = "throughline_token";

let token = sessionStorage.getItem(TOKEN_KEY);

export function isAuthenticated() {
  return Boolean(token);
}

export async function authRequired() {
  const res = await fetch(`${BASE}/auth/status`);
  const body = await res.json();
  return body.auth_required;
}

export function logout() {
  token = null;
  sessionStorage.removeItem(TOKEN_KEY);
}

export async function login(password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    throw new Error("Incorrect password");
  }
  const body = await res.json();
  token = body.token;
  sessionStorage.setItem(TOKEN_KEY, token);
}

async function request(path, options) {
  const headers = { ...(options?.headers ?? {}), Authorization: `Bearer ${token}` };
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    logout();
  }
  if (!res.ok) {
    throw new Error(`${options?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  seed: () => request("/seed", { method: "POST" }),
  customers: () => request("/customers"),
  timeline: (customerId) => request(`/timeline/${encodeURIComponent(customerId)}`),
  unresolved: () => request("/unresolved"),
  aggregate: () => request("/aggregate"),
  runDemo: (delaySeconds = 1.2) =>
    request(`/demo/run?delay_seconds=${encodeURIComponent(delaySeconds)}`, { method: "POST" }),
};

export function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws?token=${encodeURIComponent(token ?? "")}`;
}
