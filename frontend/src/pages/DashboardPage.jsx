import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { authedRequest } from "../authedRequest";
import CandleChart from "../components/CandleChart";
import LiveBadge from "../components/LiveBadge";
import MarketSelect from "../components/MarketSelect";
import TimeframeSelect from "../components/TimeframeSelect";
import { useCandles } from "../hooks/useCandles";
import { useLiveCandle } from "../hooks/useLiveCandle";
import { useSymbols } from "../hooks/useSymbols";
import { useAuthStore } from "../store/authStore";
import { decodeJwtPayload } from "../utils/jwt";

const DEFAULT_TIMEFRAME = "1h";
const BUILT_FROM_1H = ["4h", "1d"]; // the backend builds these from 1h candles
const NOTE_MODES = ["delayed", "unavailable", "closed_market"]; // live modes that deserve an explanation

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const logout = useAuthStore((state) => state.logout);

  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Market and timeframe live in the URL (?symbol=XAUUSD&timeframe=4h): they survive a refresh and can be bookmarked.
  const [params, setParams] = useSearchParams();
  const { symbols, loading: symbolsLoading, error: symbolsError } = useSymbols();
  const market = symbols.find((item) => item.symbol === params.get("symbol")) ?? symbols[0];
  const requestedTimeframe = params.get("timeframe");
  const timeframe = market?.timeframes.includes(requestedTimeframe) ? requestedTimeframe : DEFAULT_TIMEFRAME;

  const { candles, loading: candlesLoading, error: candlesError } = useCandles(market?.symbol, timeframe, 500);
  const live = useLiveCandle(market?.symbol, timeframe);
  const loading = symbolsLoading || candlesLoading;
  const chartError = symbolsError || candlesError;
  const liveCandle = loading ? null : live.candle; // wait until the closed candles are on the chart

  const precision = market?.price_precision ?? 2;
  const lastClosed = candles[candles.length - 1];
  const previousClosed = candles[candles.length - 2];
  const price = liveCandle ? liveCandle.close : lastClosed?.close;
  const reference =
    liveCandle && lastClosed && liveCandle.time > lastClosed.time ? lastClosed.close : previousClosed?.close;
  const change = price != null && reference ? ((price - reference) / reference) * 100 : null;
  const ingestTimeframe = BUILT_FROM_1H.includes(timeframe) ? "1h" : timeframe;

  const payload = accessToken ? decodeJwtPayload(accessToken) : null;
  const expiresAt = payload ? new Date(payload.exp * 1000).toLocaleTimeString() : "-";

  function setParam(name, value) {
    setParams((current) => {
      const next = new URLSearchParams(current); // keep the other parameters
      next.set(name, value);
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
              {market && (
                <>
                  <MarketSelect symbols={symbols} value={market.symbol} onChange={(value) => setParam("symbol", value)} />
                  <TimeframeSelect
                    timeframes={market.timeframes}
                    value={timeframe}
                    onChange={(value) => setParam("timeframe", value)}
                  />
                  <LiveBadge mode={live.mode} detail={live.detail} />
                </>
              )}
            </div>
            {price != null && (
              <div className="chart-price">
                {price.toFixed(precision)}
                {change !== null && (
                  <span className={change >= 0 ? "chart-change up" : "chart-change down"}>
                    {change >= 0 ? "+" : ""}
                    {change.toFixed(2)}%
                  </span>
                )}
              </div>
            )}
          </div>

          {market && (
            <p className="chart-note">
              Times in UTC
              {!market.has_volume ? " · no volume data for this market" : ""}
              {BUILT_FROM_1H.includes(timeframe) ? ` · ${timeframe} candles are built from 1h; the day starts at ${market.day_start}` : ""}
              {NOTE_MODES.includes(live.mode) && live.detail ? ` · ${live.detail}` : ""}
            </p>
          )}

          <div className="chart-box">
            <CandleChart candles={candles} precision={precision} liveCandle={liveCandle} />
            {loading && <div className="chart-overlay">Loading candles...</div>}
            {!loading && chartError && <div className="chart-overlay chart-overlay-error">{chartError}</div>}
            {!loading && !chartError && market && candles.length === 0 && (
              <div className="chart-overlay">
                No candles stored for {market.symbol} {timeframe} yet. Run: python -m scripts.ingest_candles{" "}
                {market.symbol} {ingestTimeframe} 2000
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
