export const CHANNEL_META = {
  app_events: { label: "App", color: "var(--color-channel-app)", short: "APP" },
  web_events: { label: "Web", color: "var(--color-channel-web)", short: "WEB" },
  callcenter_events: { label: "Call Center", color: "var(--color-channel-callcenter)", short: "CALL" },
  inperson_events: { label: "In Person", color: "var(--color-channel-inperson)", short: "IRL" },
  trailing_activity: { label: "Activity", color: "var(--color-ink-tertiary)", short: "ACT" },
};

export function channelMeta(channel) {
  return CHANNEL_META[channel] ?? { label: channel ?? "Unknown", color: "var(--color-ink-tertiary)", short: "?" };
}

export function formatTimestamp(ts) {
  if (ts === null || ts === undefined) return "—";
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toISOString().replace("T", " ").slice(0, 19) + "Z";
}

export function formatConfidence(c) {
  if (c === null || c === undefined) return "—";
  return c.toFixed(2);
}
