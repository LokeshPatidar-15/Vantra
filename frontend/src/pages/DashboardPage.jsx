import { useState } from "react";

import { authedRequest } from "../authedRequest";
import CandleChart from "../components/CandleChart";
import { useCandles } from "../hooks/useCandles";
import { useAuthStore } from "../store/authStore";
import { decodeJwtPayload } from "../utils/jwt";

// Day 12 adds a market selector and Day 13 a timeframe selector. For now they are fixed.
const SYMBOL = "BTCUSDT";
const TIMEFRAME = "1h";
const PRICE_PRECISION = { BTCUSDT: 2, XAUUSD: 2, EURUSD: 5 }; // decimals shown on the price axis

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const logout = useAuthStore((state) => state.logout);

  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { candles, loading, error: candlesError } = useCandles(SYMBOL, TIMEFRAME, 500);
  const precision = PRICE_PRECISION[SYMBOL];
  const last = candles[candles.length - 1];
  const previous = candles[candles.length - 2];
  const change = last && previous ? ((last.close - previous.close) / previous.close) * 100 : null;

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

      <main className="page-container wide">
        <section className="panel chart-panel">
          <div className="chart-header">
            <div>
              <span className="chart-title">{SYMBOL}</span>
              <span className="chart-sub">{TIMEFRAME} · times in UTC</span>
            </div>
            {last && (
              <div className="chart-price">
                {last.close.toFixed(precision)}
                {change !== null && (
                  <span className={change >= 0 ? "chart-change up" : "chart-change down"}>
                    {change >= 0 ? "+" : ""}
                    {change.toFixed(2)}%
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="chart-box">
            <CandleChart candles={candles} precision={precision} />
            {loading && <div className="chart-overlay">Loading candles...</div>}
            {!loading && candlesError && <div className="chart-overlay chart-overlay-error">{candlesError}</div>}
            {!loading && !candlesError && candles.length === 0 && (
              <div className="chart-overlay">
                No candles stored for {SYMBOL} {TIMEFRAME} yet. Run: python -m scripts.ingest_candles {SYMBOL}{" "}
                {TIMEFRAME} 2000
              </div>
            )}
          </div>
        </section>

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
