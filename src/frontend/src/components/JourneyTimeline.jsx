import { useEffect, useState } from "react";
import { api } from "../api.js";
import { channelMeta, formatTimestamp, formatConfidence } from "../channels.js";
import "./JourneyTimeline.css";

const SEED_HINT_STATUS = 404;

export default function JourneyTimeline() {
  const [customers, setCustomers] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [unresolved, setUnresolved] = useState(null);
  const [showUnresolved, setShowUnresolved] = useState(false);
  const [loadingCustomers, setLoadingCustomers] = useState(true);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [needsSeed, setNeedsSeed] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState(null);

  async function loadCustomers() {
    setLoadingCustomers(true);
    setError(null);
    try {
      const list = await api.customers();
      setCustomers(list);
      if (list.length === 0) {
        setNeedsSeed(true);
      } else {
        setNeedsSeed(false);
        setSelectedId((prev) => prev ?? list[0].customer_id);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingCustomers(false);
    }
  }

  useEffect(() => {
    loadCustomers();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setLoadingTimeline(true);
    api
      .timeline(selectedId)
      .then((data) => {
        if (!cancelled) setTimelineData(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingTimeline(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!showUnresolved || unresolved) return;
    api.unresolved().then(setUnresolved).catch((e) => setError(e.message));
  }, [showUnresolved, unresolved]);

  async function handleSeed() {
    setSeeding(true);
    setError(null);
    try {
      await api.seed();
      await loadCustomers();
    } catch (e) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  }

  if (loadingCustomers) {
    return <div className="loading-state">Loading customers…</div>;
  }

  if (needsSeed) {
    return (
      <div className="card empty-state">
        <h2 className="section-title">No customer data yet</h2>
        <p>
          The event pipeline hasn&apos;t been run. Seed the mock dataset to populate customer
          journeys before exploring the timeline.
        </p>
        {error && <div className="error-banner">{error}</div>}
        <button type="button" className="btn" onClick={handleSeed} disabled={seeding}>
          {seeding ? "Seeding…" : "Run /seed"}
        </button>
      </div>
    );
  }

  return (
    <div className="journey-view">
      {error && <div className="error-banner">{error}</div>}
      <div className="journey-layout">
        <aside className="card customer-picker" aria-label="Customer picker">
          <h2 className="section-title">Customers</h2>
          <p className="section-subtitle">{customers.length} resolved identities</p>
          <ul className="customer-list">
            {customers.map((c) => (
              <li key={c.customer_id}>
                <button
                  type="button"
                  className={`customer-item${c.customer_id === selectedId ? " is-active" : ""}`}
                  onClick={() => setSelectedId(c.customer_id)}
                  aria-current={c.customer_id === selectedId ? "true" : undefined}
                >
                  <span className="customer-item-id mono">{c.customer_id}</span>
                  <span className="customer-item-meta">
                    <span className="customer-item-count">{c.event_count} events</span>
                    {c.friction_count > 0 && (
                      <span className={`badge is-friction`} title={`${c.friction_count} friction flags`}>
                        {c.friction_count}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="timeline-panel">
          {loadingTimeline && <div className="loading-state">Loading timeline…</div>}
          {!loadingTimeline && timelineData && (
            <TimelinePanel customerId={selectedId} data={timelineData} />
          )}
        </section>
      </div>

      <div className="unresolved-toggle-row">
        <button
          type="button"
          className="btn-secondary btn"
          onClick={() => setShowUnresolved((v) => !v)}
        >
          {showUnresolved ? "Hide" : "Show"} unresolved events
        </button>
      </div>

      {showUnresolved && (
        <UnresolvedPanel events={unresolved} />
      )}
    </div>
  );
}

function TimelinePanel({ customerId, data }) {
  const { timeline, repeat_contacts, escalation_chain, dropoffs, friction_count } = data;

  return (
    <div className="card timeline-card">
      <div className="timeline-header">
        <div>
          <h2 className="section-title mono">{customerId}</h2>
          <p className="section-subtitle">{timeline.length} resolved events, one thread</p>
        </div>
        <FrictionSummary
          frictionCount={friction_count}
          repeatContacts={repeat_contacts}
          escalationChain={escalation_chain}
          dropoffs={dropoffs}
        />
      </div>

      {timeline.length === 0 ? (
        <p className="section-subtitle">No events for this customer.</p>
      ) : (
        <ol className="thread">
          {timeline.map((event, i) => (
            <TimelineNode key={event.id ?? `${event.raw_ref}-${i}`} event={event} isLast={i === timeline.length - 1} />
          ))}
        </ol>
      )}
    </div>
  );
}

function FrictionSummary({ frictionCount, repeatContacts, escalationChain, dropoffs }) {
  if (!frictionCount) {
    return <span className="badge">clean journey</span>;
  }
  const parts = [];
  if (repeatContacts?.length) parts.push(`${repeatContacts.length} repeat contact${repeatContacts.length > 1 ? "s" : ""}`);
  if (escalationChain) parts.push("escalation chain");
  if (dropoffs?.length) parts.push(`${dropoffs.length} drop-off${dropoffs.length > 1 ? "s" : ""}`);
  return (
    <span className="badge is-friction" title={parts.join(", ")}>
      {frictionCount} friction
    </span>
  );
}

function TimelineNode({ event, isLast }) {
  const meta = channelMeta(event.channel);
  const isUnresolved = event.method === "unresolved";

  return (
    <li className={`thread-node${isUnresolved ? " is-unresolved" : ""}`}>
      <div className="thread-node-marker-col">
        <span
          className={`thread-dot${isUnresolved ? " is-unresolved" : ""}`}
          style={{ "--dot-color": meta.color }}
        >
          {event.is_escalation && (
            <span className="escalation-ring" title="Part of an escalation chain" aria-label="escalation" />
          )}
        </span>
        {!isLast && <span className={`thread-line${isUnresolved ? " is-dashed" : ""}`} />}
      </div>

      <div className="thread-node-body">
        <div className="thread-node-top">
          <span className="thread-node-channel" style={{ color: meta.color }}>
            {meta.label}
          </span>
          <span className="thread-node-time mono">{formatTimestamp(event.timestamp)}</span>
          {event.is_escalation && <span className="tag tag-escalation">escalation</span>}
          {isUnresolved && <span className="tag tag-unresolved">unresolved</span>}
        </div>
        <div className="thread-node-action">{event.action ?? event.detail ?? "—"}</div>
        {event.detail && event.action && <div className="thread-node-detail">{event.detail}</div>}
        <div className="thread-node-bottom">
          <span className="thread-node-confidence mono">confidence {formatConfidence(event.confidence)}</span>
          <span className="thread-node-method mono">{event.method}</span>
          <span className="thread-node-ref mono">{event.raw_ref}</span>
        </div>
      </div>
    </li>
  );
}

function UnresolvedPanel({ events }) {
  if (!events) {
    return <div className="loading-state">Loading unresolved events…</div>;
  }
  return (
    <div className="card unresolved-panel">
      <h2 className="section-title">Unresolved events</h2>
      <p className="section-subtitle">
        Events the resolution engine correctly declined to force-match to any identity.
      </p>
      {events.length === 0 ? (
        <p className="section-subtitle">None — every event resolved to a customer.</p>
      ) : (
        <ul className="unresolved-list">
          {events.map((e, i) => {
            const meta = channelMeta(e.channel);
            return (
              <li key={e.id ?? `${e.raw_ref}-${i}`} className="unresolved-item">
                <span className="thread-dot is-unresolved" style={{ "--dot-color": meta.color }} />
                <span className="thread-node-channel" style={{ color: meta.color }}>
                  {meta.label}
                </span>
                <span className="thread-node-time mono">{formatTimestamp(e.timestamp)}</span>
                <span className="thread-node-action">{e.action ?? e.detail ?? "—"}</span>
                <span className="thread-node-ref mono">{e.raw_ref}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
