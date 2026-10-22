import { useEffect, useState } from "react";

import { authedRequest } from "../authedRequest";

// Loads candles from our own API. Loads again when symbol, timeframe or limit change.
export function useCandles(symbol, timeframe, limit = 500) {
  const [state, setState] = useState({ candles: [], loading: true, error: "" });

  useEffect(() => {
    let cancelled = false; // ignore an answer that arrives after the inputs changed or the page closed
    setState((current) => ({ ...current, loading: true, error: "" }));

    const query = new URLSearchParams({ symbol, timeframe, limit });
    authedRequest(`/api/market/candles?${query}`)
      .then((candles) => {
        if (!cancelled) setState({ candles, loading: false, error: "" });
      })
      .catch((err) => {
        if (!cancelled) setState({ candles: [], loading: false, error: err.message });
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe, limit]);

  return state;
}
