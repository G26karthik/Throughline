import { useState } from "react";
import JourneyTimeline from "./components/JourneyTimeline.jsx";
import AggregatePatterns from "./components/AggregatePatterns.jsx";
import ResolutionDemo from "./components/ResolutionDemo.jsx";
import LoginScreen from "./components/LoginScreen.jsx";
import { isAuthenticated, logout } from "./api.js";

const VIEWS = [
  { id: "timeline", label: "Journey Timeline" },
  { id: "aggregate", label: "Aggregate Patterns" },
  { id: "demo", label: "Resolution Demo" },
];

export default function App() {
  const [view, setView] = useState("timeline");
  const [authed, setAuthed] = useState(isAuthenticated());

  if (!authed) {
    return <LoginScreen onSuccess={() => setAuthed(true)} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <span className="app-brand-mark">Throughline</span>
          <span className="app-brand-tag">cross-channel journey stitching</span>
        </div>
        <nav className="app-nav" aria-label="Views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`app-nav-btn${view === v.id ? " is-active" : ""}`}
              aria-current={view === v.id ? "page" : undefined}
              onClick={() => setView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>
        <button
          type="button"
          className="app-nav-btn"
          onClick={() => {
            logout();
            setAuthed(false);
          }}
        >
          Log out
        </button>
      </header>

      <main className="app-main">
        {view === "timeline" && <JourneyTimeline />}
        {view === "aggregate" && <AggregatePatterns />}
        {view === "demo" && <ResolutionDemo />}
      </main>

      <footer className="app-footer">
        All data mocked/synthetic — hackathon prototype, no real AmEx systems or customer data.
      </footer>
    </div>
  );
}
