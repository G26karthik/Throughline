import { useEffect, useState } from "react";
import { api } from "../api.js";
import "./AggregatePatterns.css";

export default function AggregatePatterns() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [needsSeed, setNeedsSeed] = useState(false);
  const [seeding, setSeeding] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const agg = await api.aggregate();
      setData(agg);
      setNeedsSeed(agg.total_customers === 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSeed() {
    setSeeding(true);
    setError(null);
    try {
      await api.seed();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  }

  if (loading) {
    return <div className="loading-state">Loading aggregate patterns…</div>;
  }

  if (error) {
    return <div className="error-banner">{error}</div>;
  }

  if (needsSeed) {
    return (
      <div className="card empty-state">
        <h2 className="section-title">No aggregate data yet</h2>
        <p>Seed the mock dataset first to compute cross-customer patterns.</p>
        <button type="button" className="btn" onClick={handleSeed} disabled={seeding}>
          {seeding ? "Seeding…" : "Run /seed"}
        </button>
      </div>
    );
  }

  return <AggregateBody data={data} />;
}

export function AggregateBody({ data }) {
  const { total_customers, repeat_contact_rate_pct, escalation_rate_pct, journey_shapes, churn_correlation } = data;
  const maxCount = journey_shapes.length ? journey_shapes[0].count : 1;

  return (
    <div className="aggregate-view">
      <div className="stat-row">
        <StatCard label="Customers analyzed" value={total_customers} />
        <StatCard label="Repeat-contact rate" value={`${repeat_contact_rate_pct.toFixed(1)}%`} />
        <StatCard label="Escalation rate" value={`${escalation_rate_pct.toFixed(1)}%`} />
      </div>

      <div className="card aggregate-section">
        <h2 className="section-title">Journey shapes</h2>
        <p className="section-subtitle">Ranked by frequency — the most common path first.</p>
        <ol className="shape-list">
          {journey_shapes.map((s, i) => (
            <li key={s.shape} className="shape-row">
              <span className="shape-rank mono">{i + 1}</span>
              <span className="shape-label mono">{s.shape}</span>
              <div className="shape-bar-track">
                <div
                  className="shape-bar-fill"
                  style={{ width: `${Math.max(4, (s.count / maxCount) * 100)}%` }}
                />
              </div>
              <span className="shape-count mono">{s.count}</span>
            </li>
          ))}
        </ol>
      </div>

      <ChurnCorrelation churn={churn_correlation} />
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="card stat-card">
      <div className="stat-value mono">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function ChurnCorrelation({ churn }) {
  const {
    high_friction_customers,
    clean_customers,
    high_friction_avg_trailing_activity,
    clean_avg_trailing_activity,
    high_friction_rate_vs_clean,
  } = churn;

  const headline = buildHeadline(high_friction_rate_vs_clean);

  return (
    <div className="card aggregate-section churn-section">
      <h2 className="section-title">Friction &amp; churn correlation</h2>
      <p className="churn-headline">{headline}</p>
      <div className="churn-detail-grid">
        <div className="churn-detail">
          <span className="churn-detail-label">High-friction customers (2+ flags)</span>
          <span className="churn-detail-value mono">{high_friction_customers}</span>
        </div>
        <div className="churn-detail">
          <span className="churn-detail-label">Clean customers (0 flags)</span>
          <span className="churn-detail-value mono">{clean_customers}</span>
        </div>
        <div className="churn-detail">
          <span className="churn-detail-label">Avg trailing activity — high friction</span>
          <span className="churn-detail-value mono">{high_friction_avg_trailing_activity.toFixed(2)}</span>
        </div>
        <div className="churn-detail">
          <span className="churn-detail-label">Avg trailing activity — clean</span>
          <span className="churn-detail-value mono">{clean_avg_trailing_activity.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}

function buildHeadline(ratio) {
  if (ratio === null || ratio === undefined) {
    return "Not enough clean-journey customers yet to compute a churn comparison.";
  }
  if (ratio < 1) {
    const factor = ratio === 0 ? "∞" : (1 / ratio).toFixed(1);
    return `Customers with 2+ friction events return ${factor}x less often than clean-journey customers.`;
  }
  if (ratio === 1) {
    return "Friction events show no measurable difference in return activity yet.";
  }
  return `Customers with 2+ friction events return ${ratio.toFixed(1)}x more often — activity is inflated, likely driven by unresolved issue follow-up.`;
}
