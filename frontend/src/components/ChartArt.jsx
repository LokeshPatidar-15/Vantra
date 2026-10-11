import { useMemo } from "react";

const W = 800;
const H = 420;

// Deterministic candles (no Math.random) so the picture never changes between renders.
function buildCandles(count) {
  const candles = [];
  let prev = 50;
  for (let i = 0; i < count; i++) {
    const close = 50 + 16 * Math.sin(i / 4.2) + 9 * Math.sin(i / 1.9 + 1) + i * 0.12;
    const open = prev;
    const wick = 2 + 3 * Math.abs(Math.sin(i * 1.7));
    candles.push({
      open,
      close,
      high: Math.max(open, close) + wick,
      low: Math.min(open, close) - wick,
    });
    prev = close;
  }
  return candles;
}

export default function ChartArt() {
  const candles = useMemo(() => buildCandles(46), []);

  const min = Math.min(...candles.map((c) => c.low));
  const max = Math.max(...candles.map((c) => c.high));
  const step = W / candles.length;
  const bodyW = step * 0.55;
  const y = (value) => H - ((value - min) / (max - min)) * H;

  return (
    <svg className="chart-art" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {[0.2, 0.4, 0.6, 0.8].map((t) => (
        <line key={t} x1="0" x2={W} y1={H * t} y2={H * t} stroke="rgba(212,175,55,0.1)" strokeWidth="1" />
      ))}
      {candles.map((c, i) => {
        const x = i * step + step / 2;
        const bullish = c.close >= c.open;
        const top = y(Math.max(c.open, c.close));
        const bottom = y(Math.min(c.open, c.close));
        return (
          <g key={i} stroke="#d4af37" strokeWidth="1.2">
            <line x1={x} x2={x} y1={y(c.high)} y2={y(c.low)} />
            <rect
              x={x - bodyW / 2}
              y={top}
              width={bodyW}
              height={Math.max(1.5, bottom - top)}
              fill={bullish ? "#d4af37" : "#0b0f17"}
            />
          </g>
        );
      })}
    </svg>
  );
}
