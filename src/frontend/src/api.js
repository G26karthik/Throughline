const BASE = "";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
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
  return `${proto}//${window.location.host}/ws`;
}
