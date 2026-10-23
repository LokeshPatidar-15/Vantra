// Dropdown of markets. `symbols` is the list returned by GET /api/market/symbols.
export default function MarketSelect({ symbols, value, onChange }) {
  return (
    <select
      className="market-select"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label="Market"
    >
      {symbols.map((item) => (
        <option key={item.symbol} value={item.symbol}>
          {item.symbol} · {item.label}
        </option>
      ))}
    </select>
  );
}
