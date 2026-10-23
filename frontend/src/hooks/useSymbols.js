import { useEffect, useState } from "react";

import { authedRequest } from "../authedRequest";

// The list of markets comes from the backend, so the frontend never hardcodes it.
export function useSymbols() {
  const [state, setState] = useState({ symbols: [], loading: true, error: "" });

  useEffect(() => {
    let cancelled = false;
    authedRequest("/api/market/symbols")
      .then((symbols) => {
        if (!cancelled) setState({ symbols, loading: false, error: "" });
      })
      .catch((err) => {
        if (!cancelled) setState({ symbols: [], loading: false, error: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
