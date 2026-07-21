import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "../api.js";
import { channelMeta, formatConfidence, formatTimestamp } from "../channels.js";
import { AggregateBody } from "./AggregatePatterns.jsx";
import "./ResolutionDemo.css";

const CHANNEL_ORDER = ["app_events", "web_events", "callcenter_events", "inperson_events"];

// Fixed scatter layout so dots don't jump around when they resolve.
const SCATTER_POSITIONS = {
  app_events: { x: "18%", y: "22%" },
  web_events: { x: "72%", y: "16%" },
  callcenter_events: { x: "30%", y: "70%" },
  inperson_events: { x: "80%", y: "62%" },
};

function initialNodes() {
  const nodes = {};
  for (const ch of CHANNEL_ORDER) {
    nodes[ch] = { channel: ch, state: "pending" };
  }
  return nodes;
}

export default function ResolutionDemo() {
  const [status, setStatus] = useState("idle"); // idle | connecting | ready | running | done
  const [wsError, setWsError] = useState(null);
  const [nodes, setNodes] = useState(initialNodes);
  const [unresolvedCase, setUnresolvedCase] = useState(null);
  const [aggregate, setAggregate] = useState(null);
  const [running, setRunning] = useState(false);
  const wsRef = useRef(null);

  const connect = useCallback(() => {
    setStatus("connecting");
    let socket;
    try {
      socket = new WebSocket(wsUrl());
    } catch (e) {
      setWsError("Could not open WebSocket connection.");
      setStatus("idle");
      return;
    }
    wsRef.current = socket;

    socket.onopen = () => {
      setStatus("ready");
      setWsError(null);
    };

    socket.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      handleMessage(msg);
    };

    socket.onerror = () => {
      setWsError("WebSocket connection error — the demo needs the backend running with /ws reachable.");
    };

    socket.onclose = () => {
      setStatus((s) => (s === "running" ? "ready" : s));
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  function handleMessage(msg) {
    if (msg.type === "scattered") {
      setNodes((prev) => ({
        ...prev,
        [msg.channel]: {
          channel: msg.channel,
          state: "scattered",
          raw_ref: msg.raw_ref,
          timestamp: msg.timestamp,
        },
      }));
    } else if (msg.type === "resolved") {
      setNodes((prev) => {
        const existing = Object.values(prev).find((n) => n.raw_ref === msg.raw_ref);
        const channel = existing?.channel;
        if (!channel) return prev;
        return {
          ...prev,
          [channel]: {
            ...prev[channel],
            state: "resolved",
            customer_id: msg.customer_id,
            confidence: msg.confidence,
            method: msg.method,
          },
        };
      });
    } else if (msg.type === "unresolved_case") {
      setUnresolvedCase({ raw_ref: msg.raw_ref, reason: msg.reason });
    } else if (msg.type === "aggregate_reveal") {
      setAggregate(msg.aggregate);
      setStatus("done");
      setRunning(false);
    }
  }

  async function handleRun() {
    setRunning(true);
    setStatus("running");
    setNodes(initialNodes());
    setUnresolvedCase(null);
    setAggregate(null);
    try {
      await api.runDemo(1.2);
    } catch (e) {
      setWsError(e.message);
      setRunning(false);
      setStatus("ready");
    }
  }

  const resolvedCount = Object.values(nodes).filter((n) => n.state === "resolved").length;
  const anyScattered = Object.values(nodes).some((n) => n.state !== "pending");

  return (
    <div className="demo-view">
      <div className="demo-controls">
        <div>
          <h2 className="section-title">Signature resolution animation</h2>
          <p className="section-subtitle">
            Watch four scattered channel events resolve into one identity, live over the wire.
          </p>
        </div>
        <button type="button" className="btn" onClick={handleRun} disabled={running || status === "connecting"}>
          {running ? "Running…" : "Run demo"}
        </button>
      </div>

      {wsError && <div className="error-banner">{wsError}</div>}
      {status === "connecting" && <div className="loading-state">Connecting to /ws…</div>}

      <div className="card demo-stage">
        {!anyScattered && !running ? (
          <div className="demo-stage-empty">
            <p>Press &quot;Run demo&quot; to scatter cust_006&apos;s four channel events, then watch them resolve.</p>
          </div>
        ) : (
          <ScatterStage nodes={nodes} resolvedCount={resolvedCount} />
        )}
      </div>

      {unresolvedCase && <UnresolvedCaseCard unresolvedCase={unresolvedCase} />}

      {aggregate && (
        <div className="demo-aggregate-reveal">
          <h2 className="section-title">Aggregate reveal</h2>
          <AggregateBody data={aggregate} />
        </div>
      )}
    </div>
  );
}

function ScatterStage({ nodes, resolvedCount }) {
  const allResolved = resolvedCount === CHANNEL_ORDER.length;
  const centerX = "50%";
  const centerY = "42%";

  return (
    <div className="scatter-stage">
      <svg className="scatter-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
        {CHANNEL_ORDER.map((ch) => {
          const node = nodes[ch];
          if (node.state !== "resolved") return null;
          const pos = SCATTER_POSITIONS[ch];
          return (
            <line
              key={ch}
              className="scatter-thread"
              x1={parseFloat(pos.x)}
              y1={parseFloat(pos.y)}
              x2={parseFloat(centerX)}
              y2={parseFloat(centerY)}
            />
          );
        })}
      </svg>

      {allResolved && (
        <div className="identity-core" style={{ left: centerX, top: centerY }}>
          <span className="identity-core-label mono">cust_006</span>
        </div>
      )}

      {CHANNEL_ORDER.map((ch) => {
        const node = nodes[ch];
        const pos = SCATTER_POSITIONS[ch];
        const meta = channelMeta(ch);
        return (
          <div
            key={ch}
            className={`scatter-node state-${node.state}`}
            style={{ left: pos.x, top: pos.y, "--dot-color": meta.color }}
          >
            <span className="scatter-dot" />
            <div className="scatter-node-label">
              <span className="scatter-node-channel" style={{ color: meta.color }}>
                {meta.label}
              </span>
              {node.timestamp && <span className="scatter-node-time mono">{formatTimestamp(node.timestamp)}</span>}
              {node.state === "resolved" && (
                <span className="scatter-node-confidence mono">
                  {node.method} · {formatConfidence(node.confidence)}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function UnresolvedCaseCard({ unresolvedCase }) {
  return (
    <div className="card unresolved-case-card">
      <span className="tag tag-unresolved">unresolved</span>
      <div className="unresolved-case-body">
        <span className="mono">{unresolvedCase.raw_ref}</span>
        <p>{unresolvedCase.reason} — correctly left unlinked rather than force-matched.</p>
      </div>
    </div>
  );
}
