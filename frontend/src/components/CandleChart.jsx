import { useEffect, useRef } from "react";
import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, createChart } from "lightweight-charts";

const UP = "#22C88D";
const DOWN = "#E5484D";
const UP_SOFT = "rgba(34, 200, 141, 0.4)";
const DOWN_SOFT = "rgba(229, 72, 77, 0.4)";

// Draws candles (and volume bars when the market has volume).
// `candles`: closed candles from our API [{ time (UNIX seconds, UTC), open, high, low, close, volume }]
// `liveCandle`: the newest, still-forming candle from the WebSocket (or null)
export default function CandleChart({ candles, precision = 2, liveCandle = null }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  // 1) Create the chart once, remove it when the component goes away.
  useEffect(() => {
    const chart = createChart(containerRef.current, {
      autoSize: true, // follows the size of its container
      layout: {
        background: { type: ColorType.Solid, color: "#12161F" },
        textColor: "#7C8699",
        fontFamily: "Inter, -apple-system, 'Segoe UI', sans-serif",
      },
      grid: { vertLines: { color: "#1B2130" }, horzLines: { color: "#1B2130" } },
      rightPriceScale: { borderColor: "#232838" },
      timeScale: { borderColor: "#232838", timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderVisible: false,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.25 } });

    // Volume lives on its own invisible scale at the bottom of the chart.
    const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "" });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    chartRef.current = { chart, candleSeries, volumeSeries };
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // 2) Whenever the closed candles change, give them to the chart.
  useEffect(() => {
    if (!chartRef.current) return;
    const { chart, candleSeries, volumeSeries } = chartRef.current;

    candleSeries.applyOptions({
      priceFormat: { type: "price", precision, minMove: 1 / 10 ** precision },
    });
    candleSeries.setData(candles.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
    volumeSeries.setData(
      candles
        .filter((candle) => candle.volume) // forex and gold have no volume (null)
        .map((candle) => ({
          time: candle.time,
          value: candle.volume,
          color: candle.close >= candle.open ? UP_SOFT : DOWN_SOFT,
        }))
    );
    chart.timeScale().fitContent();
  }, [candles, precision]);

  // 3) The still-forming candle: update the newest bar in place, or add a new one.
  useEffect(() => {
    if (!chartRef.current || !liveCandle) return;
    const lastTime = candles.length ? candles[candles.length - 1].time : 0;
    if (liveCandle.time < lastTime) return; // the chart cannot go back in time

    const { candleSeries, volumeSeries } = chartRef.current;
    candleSeries.update({
      time: liveCandle.time,
      open: liveCandle.open,
      high: liveCandle.high,
      low: liveCandle.low,
      close: liveCandle.close,
    });
    if (liveCandle.volume) {
      volumeSeries.update({
        time: liveCandle.time,
        value: liveCandle.volume,
        color: liveCandle.close >= liveCandle.open ? UP_SOFT : DOWN_SOFT,
      });
    }
  }, [liveCandle, candles]);

  return <div ref={containerRef} className="chart-canvas" />;
}
