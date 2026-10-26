const LABELS = {
  connecting: "Connecting",
  live: "Live",
  delayed: "Delayed",
  closed_market: "Market closed",
  unavailable: "Live unavailable",
};

// Small status pill next to the selectors. `detail` shows when you hover over it.
export default function LiveBadge({ mode, detail }) {
  return (
    <span className={`live-badge ${mode}`} title={detail}>
      <span className="live-dot" />
      {LABELS[mode] ?? mode}
    </span>
  );
}
