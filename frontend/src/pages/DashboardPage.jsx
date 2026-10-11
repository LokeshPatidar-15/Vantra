import { useState } from "react";

import { authedRequest } from "../authedRequest";
import { useAuthStore } from "../store/authStore";
import { decodeJwtPayload } from "../utils/jwt";

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const logout = useAuthStore((state) => state.logout);

  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const payload = accessToken ? decodeJwtPayload(accessToken) : null;
  const expiresAt = payload ? new Date(payload.exp * 1000).toLocaleTimeString() : "-";

  async function callProtectedApi() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const me = await authedRequest("/api/auth/me");
      setResult(`GET /api/auth/me returned ${me.email} at ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <span className="topbar-name">Vantra</span>
          <span className="topbar-tag">TRADE SMARTER</span>
        </div>
        <div className="topbar-user">
          <span>{user?.email}</span>
          <button className="btn-outline" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <main className="page-container">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">
          Placeholder page. Charts, indicators and backtesting arrive in the next phases.
        </p>

        <section className="panel">
          <h2 className="panel-title">Session</h2>
          <dl className="kv">
            <dt>Logged in as</dt>
            <dd>{user?.email}</dd>
            <dt>User id</dt>
            <dd>{user?.id}</dd>
            <dt>Access token expires at</dt>
            <dd>{expiresAt}</dd>
          </dl>

          <button className="btn-outline" onClick={callProtectedApi} disabled={busy}>
            {busy ? "Calling..." : "Call protected API (/me)"}
          </button>

          {result && <div className="alert alert-success mt-16">{result}</div>}
          {error && <div className="alert alert-error mt-16">{error}</div>}
        </section>
      </main>
    </div>
  );
}
