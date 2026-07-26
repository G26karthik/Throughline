import { useState } from "react";
import { login } from "../api.js";

export default function LoginScreen({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(password);
      onSuccess();
    } catch {
      setError("Incorrect password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit}>
        <span className="app-brand-mark">Throughline</span>
        <p className="login-subtitle">
          Analyst dashboard — resolves real-shaped customer PII (synthetic data only).
          Enter the shared access password to continue.
        </p>
        <input
          type="password"
          autoFocus
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="login-error">{error}</p>}
        <button type="submit" disabled={submitting || !password}>
          {submitting ? "Checking..." : "Enter"}
        </button>
      </form>
    </div>
  );
}
