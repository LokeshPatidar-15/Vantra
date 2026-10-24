// Row of timeframe buttons. `timeframes` is the list returned by GET /api/market/symbols.
export default function TimeframeSelect({ timeframes, value, onChange }) {
  return (
    <div className="timeframe-pills" role="group" aria-label="Timeframe">
      {timeframes.map((item) => (
        <button
          key={item}
          type="button"
          className={item === value ? "timeframe-pill active" : "timeframe-pill"}
          onClick={() => onChange(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}
