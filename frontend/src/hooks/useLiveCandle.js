import { useEffect, useState } from "react";

import { API_BASE_URL } from "../api";
import { getFreshAccessToken } from "../authedRequest";

const WS_URL = `${API_BASE_URL.replace(/^http/, "ws")}/ws/market`; // http -> ws, https -> wss
const RETRY_DELAYS_MS = [1000, 2000, 5000, 10000];

// Keeps a WebSocket open to the backend and returns the newest still-forming candle for (symbol, timeframe).
// mode: connecting | live | delayed | closed_market | unavailable
export function useLiveCandle(symbol, timeframe) {
  const [state, setState] = useState({ candle: null, mode: "connecting", detail: "" });

  useEffect(() => {
    if (!symbol || !timeframe) return undefined;

    let socket = null;
    let retryTimer = null;
    let attempt = 0;
    let stopped = false;

    setState({ candle: null, mode: "connecting", detail: "" });

    function scheduleRetry() {
      if (stopped) return;
      setState((current) => ({ ...current, mode: "connecting" }));
      const delay = RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)];
      attempt += 1;
      retryTimer = setTimeout(connect, delay);
    }

    async function connect() {
      let token;
      try {
        token = await getFreshAccessToken();
      } catch {
        scheduleRetry();
        return;
      }
      if (stopped) return;

      socket = new WebSocket(WS_URL);
      socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "ready") {
          attempt = 0;
          socket.send(JSON.stringify({ type: "subscribe", symbol, timeframe }));
        } else if (message.type === "error") {
          setState((current) => ({ ...current, mode: "unavailable", detail: message.detail }));
        } else if (message.symbol === symbol && message.timeframe === timeframe) {
          // ignore leftovers from a market we have already switched away from
          if (message.type === "candle") setState((current) => ({ ...current, candle: message }));
          if (message.type === "status") setState((current) => ({ ...current, mode: message.mode, detail: message.detail }));
        }
      };
      socket.onclose = scheduleRetry;
    }

    connect();

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
  }, [symbol, timeframe]);

  return state;
}
