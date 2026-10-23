import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { authedRequest } from "../authedRequest";
import CandleChart from "../components/CandleChart";
import MarketSelect from "../components/MarketSelect";
import { useCandles } from "../hooks/useCandles";
import { useSymbols } from "../hooks/useSymbols";
import { useAuthStore } from "../store/authStore";
import { decodeJwtPayload } from "../utils/jwt";

// Day 13 adds a timeframe selector. For now it is fixed.
const TIMEFRAME = "1h";

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const logout = useAuthStore((state) => state.logout);

  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // The selected market lives in the URL (?symbol=XAUUSD): it survives a refresh and can be bookmarked.
  const [params, setParams] = useSearchParams();
  const { symbols, loading: symbolsLoading, error: symbolsError } = useSymbols();
  const market = symbols.find((item) => item.symbol === params.get("symbol")) ?? symbols[0];

  const { candles, loading: candlesLoading, error: candlesError } = useCandles(market?.symbol, TIMEFRAME, 500);
  const loading = symbolsLoading || candlesLoading;
  const chartError = symbolsError || candlesError;

  const precision = market?.price_precision ?? 2;
  const last = candles[candles.length - 1];
  const previous = candles[candles.length - 2];
  const change = last && previous ? ((last.close - previous.close) / previous.close) * 100 : null;

  const payload = accessToken ? decodeJwtPayload(accessToken) : null;
  const expiresAt = payload ? new Date(payload.exp * 1000).toLocaleTimeString() : "-";

  function selectMarket(symbol) {
    setParams((current) => {
      const next = new URLSearchParams(current); // keep any other parameters
      next.set("symbol", symbol);
      return next;
    });
  }

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
            <div className="chart-header-left">
              {market && <MarketSelect symbols={symbols} value={market.symbol} onChange={selectMarket} />}
              <span className="chart-sub">
                {TIMEFRAME} · times in UTC
                {market && !market.has_volume ? " · no volume data for this market" : ""}
              </span>
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
            {!loading && chartError && <div className="chart-overlay chart-overlay-error">{chartError}</div>}
            {!loading && !chartError && market && candles.length === 0 && (
              <div className="chart-overlay">
                No candles stored for {market.symbol} {TIMEFRAME} yet. Run: python -m scripts.ingest_candles{" "}
                {market.symbol} {TIMEFRAME} 2000
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
